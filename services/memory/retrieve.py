"""
مرحلة Retrieve (ADR-019، M2b): استرجاع **هجين** لكل مخزن — dense (pgvector cosine على halfvec
عبر HNSW) + lexical (tsvector FTS مع normalize_ar) — ثم دمج عبر المخازن بـ **RRF**.
relevance-first، بلا LLM وبلا تصنيف-نيّة. fail-soft: إن تعذّر تضمين الاستعلام نكتفي باللفظي.
يُرجِع مرشّحين مُرتّبين [(MemoryItem, rrf_score)]؛ الإسقاط/الترتيب النهائي لاحقاً (Rank/Compose).
"""

from __future__ import annotations

import asyncio
from typing import Any

from arabic import normalize_ar
from embeddings import embed_one, to_pgvector
from models import MemoryItem
from normalize import row_to_memory_item

DEFAULT_TABLES = ("user_memory", "conversation_memory", "file_memory")
RRF_K = 60  # ثابت RRF القياسي

# الأعمدة التي يحتاجها Normalize (نتجنّب جلب المتجه الخام وcontent_tsv — حِمل كبير بلا داعٍ)
_COLS = (
    "item_id, source_type, user_id, conversation_id, file_id, chunk_no, content, "
    "embedding_model_version, origin, writer, source_ref, content_hash, confidence, "
    "importance, created_at, updated_at, last_accessed, token_estimate, status, metadata"
)


async def _dense(pool: Any, table: str, user_id: str, qvec_literal: str, k: int) -> list:
    return await pool.fetch(
        f"SELECT {_COLS} FROM memory.{table} "
        "WHERE user_id=$1 AND status <> 'deleted' AND embedding IS NOT NULL "
        "ORDER BY embedding <=> $2::halfvec LIMIT $3",
        user_id,
        qvec_literal,
        k,
    )


async def _lexical(pool: Any, table: str, user_id: str, norm_query: str, k: int) -> list:
    return await pool.fetch(
        f"SELECT {_COLS} FROM memory.{table} "
        "WHERE user_id=$1 AND status <> 'deleted' "
        "AND content_tsv @@ plainto_tsquery('simple', $2) "
        "ORDER BY ts_rank(content_tsv, plainto_tsquery('simple', $2)) DESC LIMIT $3",
        user_id,
        norm_query,
        k,
    )


def _rrf_merge(ranked_lists: list[list], top_k: int) -> list[tuple[MemoryItem, float]]:
    """دمج Reciprocal Rank Fusion: score(item) = Σ 1/(K + rank). يزيل التكرار بالـ item_id."""
    scores: dict[str, float] = {}
    rows_by_key: dict[str, Any] = {}
    for rows in ranked_lists:
        for rank, row in enumerate(rows):
            key = str(row["item_id"])
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
            rows_by_key.setdefault(key, row)
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [(row_to_memory_item(rows_by_key[k]), score) for k, score in ordered]


async def retrieve(
    pool: Any,
    user_id: str,
    query: str,
    top_k: int = 8,
    per_store_k: int = 10,
    tables: tuple[str, ...] = DEFAULT_TABLES,
) -> list[tuple[MemoryItem, float]]:
    """استرجاع هجين عبر المخازن المعطاة (كلها محصورة بـ user_id) → مرشّحون مدموجون بـ RRF."""
    norm_query = normalize_ar(query)
    qvec_literal: str | None = None
    try:
        qvec_literal = to_pgvector(await embed_one(norm_query))
    except Exception:  # noqa: BLE001 — fail-soft: بلا تضمين نكتفي بالبحث اللفظي
        qvec_literal = None

    tasks = []
    for t in tables:
        if qvec_literal:
            tasks.append(_dense(pool, t, user_id, qvec_literal, per_store_k))
        tasks.append(_lexical(pool, t, user_id, norm_query, per_store_k))
    ranked_lists = await asyncio.gather(*tasks)
    return _rrf_merge(ranked_lists, top_k)
