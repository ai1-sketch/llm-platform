"""اختبارات مرحلة Normalize (ADR-019، M1) — صفّ DB → MemoryItem للمخازن الثلاثة."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from normalize import row_to_memory_item


def _row(**over):
    base = {
        "item_id": uuid4(),
        "source_type": "conversation_chunk",
        "user_id": "u1",
        "conversation_id": "c1",
        "file_id": None,
        "chunk_no": 3,
        "content": "نص المحادثة",
        "embedding_model_version": None,
        "origin": "conversation_turn",
        "writer": "ingest_job",
        "source_ref": "msg-9",
        "content_hash": "abc123",
        "confidence": 1.0,
        "importance": 0.4,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "last_accessed": None,
        "token_estimate": 12,
        "status": "active",
        "metadata": {},
    }
    base.update(over)
    return base


def test_basic_mapping():
    m = row_to_memory_item(_row())
    assert m.text == "نص المحادثة"  # content -> text
    assert m.scope.user_id == "u1"
    assert m.scope.conversation_id == "c1"
    assert m.scope.chunk_no == 3
    assert m.source_type == "conversation_chunk"
    assert m.provenance.origin == "conversation_turn"
    assert m.provenance.source_ref == "msg-9"
    assert m.provenance.content_hash == "abc123"
    assert m.token_estimate == 12
    assert m.embedding_ref.present is False


def test_embedding_present_sets_ref():
    m = row_to_memory_item(_row(embedding_model_version="qwen3-emb-0.6b-q8@1024"))
    assert m.embedding_ref.present is True
    assert m.embedding_ref.dim == 1024
    assert m.embedding_ref.model_version == "qwen3-emb-0.6b-q8@1024"


def test_metadata_json_string_parsed():
    m = row_to_memory_item(_row(metadata=json.dumps({"page": 2})))
    assert m.metadata == {"page": 2}


def test_metadata_bad_string_is_safe():
    m = row_to_memory_item(_row(metadata="not-json"))
    assert m.metadata == {}


def test_missing_content_becomes_empty():
    m = row_to_memory_item(_row(content=None))
    assert m.text == ""
