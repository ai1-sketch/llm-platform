"""
عقد `MemoryItem` — المغلّف المصدر-المحايد للـ Context Engine (ADR-019، M1).
كل مخزن (user/conversation/file) يُطبَّع إلى هذا الشكل عبر `normalize`؛ المراحل التالية
(Rank/Compose) لا ترى شكل الصفّ الأصلي. يحمل `embedding_ref` (وصفاً) لا متجهات خام —
متجهات الـ dedup تُمرَّر عبر قناة جانبية (M3). reflection محجوز لـ v2 (بلا صفوف الآن).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

SourceType = Literal["user_fact", "conversation_chunk", "document_chunk", "reflection"]
Status = Literal["active", "archived", "superseded", "deleted"]
Origin = Literal["user_explicit", "conversation_turn", "file_ingest", "model_reflection"]
Writer = Literal["hook", "ingest_job", "consolidation_job"]


class Scope(BaseModel):
    """مفاتيح العزل/الموقع. user_id إلزامي دائماً (شرط RLS/WHERE)."""

    user_id: str
    conversation_id: str | None = None
    file_id: str | None = None
    chunk_no: int | None = None


class EmbeddingRef(BaseModel):
    """وصف التضمين فقط (لا متجه خام في العقد عبر المراحل)."""

    model_version: str | None = None
    dim: int | None = None
    present: bool = False


class Provenance(BaseModel):
    """مصدر العنصر — أساس مكافحة التسميم + تدقيق GDPR + مفتاح dedup."""

    origin: Origin
    writer: Writer
    source_ref: str | None = None  # message_id | f"{sha256}:p{page}"
    ingested_at: datetime | None = None
    content_hash: str | None = None  # sha256 للنص المُطبَّع


class MemoryItem(BaseModel):
    """العنصر الموحّد الذي تنتجه مرحلة Normalize وتستهلكه Rank/Compose."""

    item_id: UUID
    source_type: SourceType
    scope: Scope
    text: str
    embedding_ref: EmbeddingRef = Field(default_factory=EmbeddingRef)
    provenance: Provenance
    confidence: float = 1.0
    importance: float = 0.5
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_accessed: datetime | None = None
    token_estimate: int = 0
    status: Status = "active"
    metadata: dict = Field(default_factory=dict)
