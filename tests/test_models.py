"""اختبارات عقد MemoryItem (ADR-019، M1) — تحقّق + قيم افتراضية + بذرة reflection."""

from uuid import uuid4

import pytest
from models import EmbeddingRef, MemoryItem, Provenance, Scope
from pydantic import ValidationError


def _minimal() -> MemoryItem:
    return MemoryItem(
        item_id=uuid4(),
        source_type="user_fact",
        scope=Scope(user_id="u1"),
        text="hello",
        provenance=Provenance(origin="user_explicit", writer="hook"),
    )


def test_minimal_defaults():
    m = _minimal()
    assert m.confidence == 1.0
    assert m.importance == 0.5
    assert m.status == "active"
    assert m.token_estimate == 0
    assert m.metadata == {}
    assert isinstance(m.embedding_ref, EmbeddingRef)
    assert m.embedding_ref.present is False
    assert m.scope.user_id == "u1"


def test_user_id_required():
    with pytest.raises(ValidationError):
        Scope()  # type: ignore[call-arg]  # user_id إلزامي


def test_source_type_literal_enforced():
    with pytest.raises(ValidationError):
        MemoryItem(
            item_id=uuid4(),
            source_type="bogus",  # type: ignore[arg-type]
            scope=Scope(user_id="u1"),
            text="x",
            provenance=Provenance(origin="user_explicit", writer="hook"),
        )


def test_reflection_seam_reserved():
    # reflection نوع محجوز صالح لـ v2 (بثقة أقل) — العقد يتركه مفتوحاً بلا صفوف الآن
    m = MemoryItem(
        item_id=uuid4(),
        source_type="reflection",
        scope=Scope(user_id="u1"),
        text="user seems to work in law",
        provenance=Provenance(origin="model_reflection", writer="consolidation_job"),
        confidence=0.6,
    )
    assert m.source_type == "reflection"
    assert m.confidence == 0.6
