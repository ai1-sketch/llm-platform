"""
خدمة الذاكرة (L1) لـ llm-platform — ذاكرة per-user صريحة، معزولة بـ user_id.
كل استعلام مُقيّد بـ user_id (عزل إلزامي). تُنادى من LiteLLM hook عبر HTTP داخل الشبكة.
قابلة للترقية لاحقاً لـ Mem0/RAG (ADR-012) دون تغيير عقد الـ hook.
"""
import os
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

DB_URL = os.environ.get("MEMORY_DATABASE_URL")
if not DB_URL:  # fail-fast (R-ERR-02): لا نبدأ بإعداد ناقص
    raise SystemExit("MEMORY_DATABASE_URL مفقود — لا يمكن بدء خدمة الذاكرة")

pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)
    yield
    if pool:
        await pool.close()


app = FastAPI(title="llm-platform memory", lifespan=lifespan)


class AddReq(BaseModel):
    user_id: str = Field(min_length=1)
    content: str = Field(min_length=1)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/memories")
async def list_memories(user_id: str = Query(min_length=1), limit: int = 50):
    rows = await pool.fetch(
        "SELECT id, content FROM memory.user_memory WHERE user_id=$1 "
        "ORDER BY created_at DESC LIMIT $2",
        user_id, min(limit, 200),
    )
    return {"memories": [{"id": r["id"], "content": r["content"]} for r in rows]}


@app.post("/v1/memories")
async def add_memory(req: AddReq):
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="content فارغ بعد التشذيب")
    row = await pool.fetchrow(
        "INSERT INTO memory.user_memory(user_id, content) VALUES($1, $2) RETURNING id",
        req.user_id, content,
    )
    return {"id": row["id"], "stored": True}


@app.delete("/v1/memories/{mem_id}")
async def delete_one(mem_id: int, user_id: str = Query(min_length=1)):
    res = await pool.execute(
        "DELETE FROM memory.user_memory WHERE id=$1 AND user_id=$2", mem_id, user_id
    )
    return {"result": res}


@app.delete("/v1/memories")
async def clear_all(user_id: str = Query(min_length=1)):
    res = await pool.execute("DELETE FROM memory.user_memory WHERE user_id=$1", user_id)
    return {"result": res}
