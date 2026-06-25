"""
مرحلة Normalize (ADR-019، M1): تحوّل صفّاً من أي مخزن (user/conversation/file) إلى `MemoryItem`.
الجداول الثلاثة تشترك في عقد الأعمدة (schema.py) → مُحوِّل واحد يكفي ويضمن تطابق العقد.
بعد هذه المرحلة لا ترى المراحل التالية (Rank/Compose) شكل الصفّ الأصلي. content→text، metadata→dict.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from models import EmbeddingRef, MemoryItem, Provenance, Scope
from schema import EMBED_DIM


def _as_uuid(v: Any) -> UUID:
    return v if isinstance(v, UUID) else UUID(str(v))


def _as_dict(v: Any) -> dict:
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v:
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            return {}
    return {}


def row_to_memory_item(row: Mapping[str, Any]) -> MemoryItem:
    """صفّ DB (asyncpg Record أو dict) → MemoryItem. يدعم المخازن الثلاثة (عقد أعمدة موحّد)."""
    model_version = row.get("embedding_model_version")
    return MemoryItem(
        item_id=_as_uuid(row.get("item_id")),
        source_type=row.get("source_type", "user_fact"),
        scope=Scope(
            user_id=row.get("user_id"),
            conversation_id=row.get("conversation_id"),
            file_id=row.get("file_id"),
            chunk_no=row.get("chunk_no"),
        ),
        text=row.get("content") or "",
        embedding_ref=EmbeddingRef(
            model_version=model_version,
            dim=EMBED_DIM if model_version else None,
            present=bool(model_version),
        ),
        provenance=Provenance(
            origin=row.get("origin", "user_explicit"),
            writer=row.get("writer", "hook"),
            source_ref=row.get("source_ref"),
            ingested_at=row.get("created_at"),
            content_hash=row.get("content_hash"),
        ),
        confidence=row.get("confidence", 1.0),
        importance=row.get("importance", 0.5),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        last_accessed=row.get("last_accessed"),
        token_estimate=row.get("token_estimate") or 0,
        status=row.get("status", "active"),
        metadata=_as_dict(row.get("metadata")),
    )
