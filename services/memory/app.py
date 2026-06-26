"""
خدمة الذاكرة / Context Engine لـ llm-platform (ADR-019). معزولة بـ user_id (WHERE user_id إلزامي).
البنية (M1): المخطط في schema.py (3 مخازن user/conversation/file بعقد أعمدة موحّد)، عقد
MemoryItem في models.py، مرحلة Normalize في normalize.py. النقاط الحالية = L1 (حقائق المستخدم)؛
الاسترجاع/التضمين/الـ Orchestrator في مراحل لاحقة (M2+). تُنادى من LiteLLM hook عبر HTTP داخلي.
"""

import hashlib
import os
import time
import uuid
from contextlib import asynccontextmanager

import asyncpg
from arabic import normalize_ar
from embeddings import EMBEDDING_MODEL_VERSION, embed_one, to_pgvector
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from obs import log as _log
from pydantic import BaseModel, Field
from rank import rank_items
from retrieve import retrieve
from schema import SCHEMA_DDL

from compose import compose_context

DB_URL = os.environ.get("MEMORY_DATABASE_URL")
if not DB_URL:  # fail-fast (R-ERR-02): لا نبدأ بإعداد ناقص — خطأ يسمّي المتغيّر
    _log("CRITICAL", "CONFIG_MISSING_KEY", "MEMORY_DATABASE_URL مفقود — لا يمكن بدء خدمة الذاكرة")
    raise SystemExit(1)

ASSEMBLE_TOP_K = int(os.environ.get("CTX_RETRIEVAL_TOP_K", "12"))  # config-driven (المواصفة §10)
CAPTURE_MAX_CHARS = int(
    os.environ.get("CTX_CAPTURE_MAX_CHARS", "2000")
)  # سقف طول الدور المُلتقَط (M4b)
CONVERSATION_IMPORTANCE = float(
    os.environ.get("CTX_CONVERSATION_IMPORTANCE", "0.4")
)  # < حقائق المستخدم

pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global pool
    # نُنشئ المخطط عند الإقلاع (لا نبتلع الفشل: قاعدة معطوبة تمنع بدء الخدمة). الفشل يخرج
    # **بصوت** كخطأ CONFIG مهيكل لا stack-trace خام (ADR-020، R-ERR-01/21).
    try:
        pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA_DDL)
    except Exception as e:  # noqa: BLE001 — نسجّل خطأ إقلاع مهيكل ثم نُفشل بوضوح (لا ابتلاع)
        _log(
            "CRITICAL",
            "BOOTSTRAP_FAILED",
            f"تعذّر تهيئة قاعدة الذاكرة (pgvector/DDL): {type(e).__name__}",
            remediation="تأكّد أن صورة postgres = pgvector وأن الامتدادات قابلة للإنشاء (ADR-020).",
        )
        raise SystemExit(1) from e
    _log("INFO", "SCHEMA_READY", "memory schema ensured (idempotent bootstrap)")
    yield
    if pool:
        await pool.close()


app = FastAPI(title="llm-platform memory", lifespan=lifespan)


@app.middleware("http")
async def _request_log(request: Request, call_next):
    """سجل وصول JSON بـ request_id ممرَّر من البوّابة (R-ERR-15/19). يتخطّى /health (ضجيج دوري)."""
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    if request.url.path == "/health":
        return await call_next(request)
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:  # noqa: BLE001 — نسجّل بـ code ثم نعيد الرفع (R-ERR-08)، لا ابتلاع صامت
        _log(
            "ERROR", "REQUEST_UNHANDLED", f"{request.method} {request.url.path} raised", request_id
        )
        raise
    _log(
        "INFO",
        "REQUEST",
        f"{request.method} {request.url.path} -> {response.status_code}",
        request_id,
        status=response.status_code,
        duration_ms=round((time.monotonic() - start) * 1000, 1),
    )
    response.headers["X-Request-ID"] = request_id
    return response


def _error_body(code: str, message: str, type_: str, request_id: str | None) -> dict:
    """شكل خطأ موحّد متوافق مع OpenAI (R-ERR-04/06): code + message + request_id + type."""
    return {"error": {"code": code, "message": message, "type": type_, "request_id": request_id}}


@app.exception_handler(HTTPException)
async def _http_exc_handler(request: Request, exc: HTTPException) -> JSONResponse:
    rid = request.headers.get("x-request-id")
    body = _error_body("HTTP_ERROR", str(exc.detail), "invalid_request_error", rid)
    return JSONResponse(
        status_code=exc.status_code, content=body, headers={"X-Request-ID": rid or ""}
    )


@app.exception_handler(Exception)
async def _unhandled_exc_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = request.headers.get("x-request-id")
    _log("ERROR", "INTERNAL_ERROR", f"unhandled {type(exc).__name__} at {request.url.path}", rid)
    body = _error_body("INTERNAL_ERROR", "internal error", "internal_error", rid)
    return JSONResponse(status_code=500, content=body, headers={"X-Request-ID": rid or ""})


class AddReq(BaseModel):
    user_id: str = Field(min_length=1)
    content: str = Field(min_length=1)


class RetrieveReq(BaseModel):
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    top_k: int = 8


class CaptureTurn(BaseModel):
    role: str = Field(min_length=1)
    content: str
    source_ref: str | None = None  # message_id للـ provenance


class CaptureReq(BaseModel):
    user_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    turns: list[CaptureTurn]


class AssembleReq(BaseModel):
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    # الـ hook يمرّر دائماً ميزانية واعية بالنافذة (ADR-021)؛ هذا الافتراضي fallback للنداء المباشر
    budget_tokens: int = 1500


def _require_pool() -> "asyncpg.Pool":
    """يضمن تهيئة الـ pool (يُفشل بوضوح لو نودي قبل lifespan) — ويُرضي فحص الأنواع."""
    if pool is None:
        raise RuntimeError("pool not initialized")
    return pool


async def _embed_or_none(norm: str, rid: str | None) -> tuple[str | None, str | None]:
    """تضمين fail-soft مشترك: يُرجِع (vec_literal, model_version) أو (None, None) مع سجلّ عند العطل.
    العنصر يُخزَّن بلا متجه ويُسترجَع لفظياً — العطل لا يُفقد البيانات (R-ERR، ADR-019)."""
    try:
        return to_pgvector(await embed_one(norm, request_id=rid)), EMBEDDING_MODEL_VERSION
    except Exception as e:  # noqa: BLE001 — fail-soft مقصود؛ نسجّله بـ code ولا نكسر الكتابة
        _log("WARN", "EMBED_FAILED", f"stored without vector: {type(e).__name__}", rid)
        return None, None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/memories")
async def list_memories(user_id: str = Query(min_length=1), limit: int = 50):
    rows = await _require_pool().fetch(
        "SELECT id, content FROM memory.user_memory WHERE user_id=$1 "
        "ORDER BY created_at DESC LIMIT $2",
        user_id,
        min(limit, 200),
    )
    return {"memories": [{"id": r["id"], "content": r["content"]} for r in rows]}


@app.post("/v1/memories")
async def add_memory(req: AddReq, request: Request):
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="content فارغ بعد التشذيب")
    norm = normalize_ar(content)
    content_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    token_estimate = max(
        1, len(content) // 4
    )  # تقدير كتابة-وقت تقريبي؛ ميزانية القراءة الفعلية = byte-count في Compose (ADR-021)
    rid = request.headers.get("x-request-id")  # سلسلة معرّف الطلب للبوّابة (R-ERR-19)
    vec_literal, model_version = await _embed_or_none(norm, rid)  # fail-soft مشترك
    row = await _require_pool().fetchrow(
        "INSERT INTO memory.user_memory "
        "(user_id, content, content_hash, token_estimate, embedding, "
        " embedding_model_version, content_tsv, origin, writer) "
        "VALUES($1, $2, $3, $4, $5::halfvec, $6, to_tsvector('simple', $7), "
        " 'user_explicit', 'hook') RETURNING id",
        req.user_id,
        content,
        content_hash,
        token_estimate,
        vec_literal,
        model_version,
        norm,
    )
    return {"id": row["id"], "stored": True, "embedded": vec_literal is not None}


@app.delete("/v1/memories/{mem_id}")
async def delete_one(mem_id: int, user_id: str = Query(min_length=1)):
    res = await _require_pool().execute(
        "DELETE FROM memory.user_memory WHERE id=$1 AND user_id=$2", mem_id, user_id
    )
    return {"result": res}


@app.delete("/v1/memories")
async def clear_all(user_id: str = Query(min_length=1)):
    res = await _require_pool().execute("DELETE FROM memory.user_memory WHERE user_id=$1", user_id)
    return {"result": res}


@app.post("/v1/retrieve")
async def retrieve_endpoint(req: RetrieveReq, request: Request):
    """استرجاع هجين (dense+lexical+RRF) — مرشّحون مُرتّبون. يستهلكه الـ Orchestrator لاحقاً (M4)."""
    rid = request.headers.get("x-request-id")
    results = await retrieve(
        _require_pool(), req.user_id, req.query, top_k=req.top_k, request_id=rid
    )
    return {
        "results": [
            {
                "item_id": str(m.item_id),
                "source_type": m.source_type,
                "text": m.text,
                "score": round(score, 6),
            }
            for m, score in results
        ]
    }


@app.post("/v1/assemble")
async def assemble_endpoint(req: AssembleReq, request: Request):
    """مسار القراءة الكامل: retrieve → rank → compose. يُرجِع كتلة سياق ضمن الميزانية (M3)."""
    rid = request.headers.get("x-request-id")
    candidates = await retrieve(
        _require_pool(), req.user_id, req.query, top_k=ASSEMBLE_TOP_K, request_id=rid
    )
    ranked = rank_items(candidates)
    result = compose_context(ranked, req.budget_tokens)
    return {
        "context_block": result.block,
        "item_count": len(result.items),
        "tokens": result.tokens,
        "budget_tokens": req.budget_tokens,
    }


async def _store_turn(
    user_id: str, conversation_id: str, turn: CaptureTurn, rid: str | None
) -> bool:
    """يخزّن دوراً في conversation_memory (idempotent بـ ON CONFLICT). True إن أُدرِج فعلاً."""
    content = turn.content.strip()[:CAPTURE_MAX_CHARS]
    if not content:
        return False
    norm = normalize_ar(content)
    content_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    token_estimate = max(1, len(content) // 4)
    vec_literal, model_version = await _embed_or_none(norm, rid)
    row = await _require_pool().fetchrow(
        "INSERT INTO memory.conversation_memory "
        "(user_id, conversation_id, content, content_hash, token_estimate, embedding, "
        " embedding_model_version, content_tsv, source_type, origin, writer, source_ref, "
        " importance) "
        "VALUES($1, $2, $3, $4, $5, $6::halfvec, $7, to_tsvector('simple', $8), "
        " 'conversation_chunk', 'conversation_turn', 'hook', $9, $10) "
        "ON CONFLICT (user_id, conversation_id, content_hash) DO NOTHING RETURNING id",
        user_id,
        conversation_id,
        content,
        content_hash,
        token_estimate,
        vec_literal,
        model_version,
        norm,
        turn.source_ref,
        CONVERSATION_IMPORTANCE,
    )
    return row is not None


@app.post("/v1/conversation/capture")
async def capture_conversation(req: CaptureReq, request: Request):
    """التقاط أدوار المحادثة (M4b، ذاكرة عرضية) في conversation_memory؛ dedup بـ content_hash."""
    rid = request.headers.get("x-request-id")
    captured = 0
    for turn in req.turns:
        if await _store_turn(req.user_id, req.conversation_id, turn, rid):
            captured += 1
    return {"captured": captured, "received": len(req.turns)}
