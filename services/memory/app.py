"""
خدمة الذاكرة (L1) لـ llm-platform — ذاكرة per-user صريحة، معزولة بـ user_id.
كل استعلام مُقيّد بـ user_id (عزل إلزامي). تُنادى من LiteLLM hook عبر HTTP داخل الشبكة.
قابلة للترقية لاحقاً لـ Mem0/RAG (ADR-012) دون تغيير عقد الـ hook.
"""

import json
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import asyncpg
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field


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

# bootstrap idempotent للمخطط — يطابق التعريف القائم (bigserial PK + index على user_id).
# يضمن عمل الذاكرة على volume نظيف بلا خطوة يدوية (CONSTITUTION §3 / DoD). فشله = فشل إقلاع صاخب.
SCHEMA_DDL = """
CREATE SCHEMA IF NOT EXISTS memory;
CREATE TABLE IF NOT EXISTS memory.user_memory (
    id         bigserial   PRIMARY KEY,
    user_id    text        NOT NULL,
    content    text        NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_user_memory_user ON memory.user_memory (user_id);
"""


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
    row = await _require_pool().fetchrow(
        "INSERT INTO memory.user_memory(user_id, content) VALUES($1, $2) RETURNING id",
        req.user_id,
        content,
    )
    return {"id": row["id"], "stored": True}


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
