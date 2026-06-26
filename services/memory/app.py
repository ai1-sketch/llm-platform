"""
خدمة الذاكرة / Context Engine لـ llm-platform (ADR-019). معزولة بـ user_id (WHERE user_id إلزامي).
البنية (M1): المخطط في schema.py (3 مخازن user/conversation/file بعقد أعمدة موحّد)، عقد
MemoryItem في models.py، مرحلة Normalize في normalize.py. النقاط الحالية = L1 (حقائق المستخدم)؛
الاسترجاع/التضمين/الـ Orchestrator في مراحل لاحقة (M2+). تُنادى من LiteLLM hook عبر HTTP داخلي.
"""

import hashlib
import json
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import asyncpg
from arabic import normalize_ar
from embeddings import EMBEDDING_MODEL_VERSION, embed_one, to_pgvector
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field
from rank import rank_items
from retrieve import retrieve
from schema import SCHEMA_DDL

from compose import compose_context


def _log(level, code, message, request_id=None, **extra):
    """سطر سجل JSON واحد (R-ERR-14). service=memory. لا محتوى/أسرار (R-ERR-18)."""
    rec = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": level,
        "service": "memory",
        "code": code,
        "message": message,
    }
    if request_id:
        rec["request_id"] = request_id
    rec.update(extra)
    print(json.dumps(rec, ensure_ascii=False), file=sys.stdout, flush=True)


DB_URL = os.environ.get("MEMORY_DATABASE_URL")
if not DB_URL:  # fail-fast (R-ERR-02): لا نبدأ بإعداد ناقص — خطأ يسمّي المتغيّر
    _log("CRITICAL", "CONFIG_MISSING_KEY", "MEMORY_DATABASE_URL مفقود — لا يمكن بدء خدمة الذاكرة")
    raise SystemExit(1)

pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)
    # نُنشئ المخطط عند الإقلاع (لا نبتلع الفشل: قاعدة معطوبة يجب أن تمنع بدء الخدمة).
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_DDL)
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


class AddReq(BaseModel):
    user_id: str = Field(min_length=1)
    content: str = Field(min_length=1)


class RetrieveReq(BaseModel):
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    top_k: int = 8


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
async def add_memory(req: AddReq):
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="content فارغ بعد التشذيب")
    norm = normalize_ar(content)
    content_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    token_estimate = max(
        1, len(content) // 4
    )  # تقدير كتابة-وقت تقريبي؛ ميزانية القراءة الفعلية = byte-count في Compose (ADR-021)
    # التضمين fail-soft: عطل خدمة التضمين لا يُفقد الحقيقة (تُخزَّن بلا متجه وتُسترجَع لفظياً)
    vec_literal: str | None = None
    model_version: str | None = None
    try:
        vec_literal = to_pgvector(await embed_one(norm))
        model_version = EMBEDDING_MODEL_VERSION
    except Exception as e:  # noqa: BLE001 — fail-soft مقصود؛ نسجّله ولا نكسر الكتابة
        _log("WARN", "EMBED_FAILED", f"stored without vector: {type(e).__name__}")
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
async def retrieve_endpoint(req: RetrieveReq):
    """استرجاع هجين (dense+lexical+RRF) — مرشّحون مُرتّبون. يستهلكه الـ Orchestrator لاحقاً (M4)."""
    results = await retrieve(_require_pool(), req.user_id, req.query, top_k=req.top_k)
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
async def assemble_endpoint(req: AssembleReq):
    """مسار القراءة الكامل: retrieve → rank → compose. يُرجِع كتلة سياق ضمن الميزانية (M3)."""
    candidates = await retrieve(_require_pool(), req.user_id, req.query, top_k=12)
    ranked = rank_items(candidates)
    result = compose_context(ranked, req.budget_tokens)
    return {
        "context_block": result.block,
        "item_count": len(result.items),
        "tokens": result.tokens,
        "budget_tokens": req.budget_tokens,
    }
