"""اختبارات Retrieve (ADR-019، M2b) — دمج RRF + fail-soft (لفظي بلا تضمين)."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import retrieve as R


def _row(item_id, content="x"):
    return {
        "item_id": item_id,
        "source_type": "user_fact",
        "user_id": "u1",
        "conversation_id": None,
        "file_id": None,
        "chunk_no": None,
        "content": content,
        "embedding_model_version": "v",
        "origin": "user_explicit",
        "writer": "hook",
        "source_ref": None,
        "content_hash": "h",
        "confidence": 1.0,
        "importance": 0.5,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "last_accessed": None,
        "token_estimate": 3,
        "status": "active",
        "metadata": {},
    }


def test_rrf_merge_dedups_and_ranks_shared_top():
    a, b, c = uuid4(), uuid4(), uuid4()
    dense = [_row(a), _row(b)]  # a@0, b@1
    lexical = [_row(b), _row(c)]  # b@0, c@1
    out = R._rrf_merge([dense, lexical], top_k=5)
    keys = [str(m.item_id) for m, _ in out]
    assert keys[0] == str(b)  # ظهر في القائمتين → أعلى دمج
    assert set(keys) == {str(a), str(b), str(c)}  # مُزال التكرار
    assert len(keys) == 3


def test_rrf_merge_returns_memory_items():
    a = uuid4()
    out = R._rrf_merge([[_row(a, "hello")]], top_k=5)
    item, score = out[0]
    assert item.text == "hello"
    assert score > 0


def test_retrieve_lexical_only_when_embed_fails(monkeypatch):
    a = uuid4()
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[_row(a, "hello")])

    async def _boom(_t, request_id=None):
        raise RuntimeError("embeddings down")

    monkeypatch.setattr(R, "embed_query", _boom)
    out = asyncio.run(R.retrieve(pool, "u1", "hello", tables=("user_memory",)))
    assert len(out) == 1 and str(out[0][0].item_id) == str(a)
    assert pool.fetch.await_count == 1  # تضمين فشل → استعلام لفظي واحد فقط (لا dense)


def test_retrieve_logs_on_embed_failure(monkeypatch, capsys):
    # fail-soft صاخب: فشل تضمين الاستعلام يُسجَّل (EMBED_QUERY_FAILED) مع request_id (R-ERR-10)
    a = uuid4()
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[_row(a, "hello")])

    async def _boom(_t, request_id=None):
        raise RuntimeError("down")

    monkeypatch.setattr(R, "embed_query", _boom)
    asyncio.run(R.retrieve(pool, "u1", "hello", tables=("user_memory",), request_id="rid-x"))
    out = capsys.readouterr().out
    assert "EMBED_QUERY_FAILED" in out and "rid-x" in out


def test_retrieve_runs_dense_and_lexical_when_embedded(monkeypatch):
    a = uuid4()
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[_row(a)])

    async def _vec(_t, request_id=None):
        return [0.1] * 1024

    monkeypatch.setattr(R, "embed_query", _vec)
    asyncio.run(R.retrieve(pool, "u1", "hello", tables=("user_memory",)))
    assert pool.fetch.await_count == 2  # dense + lexical لكل مخزن
