"""اختبارات Compose/Budget (ADR-019، M3) — dedup، عدّ محافظ، عدم تجاوز الميزانية."""

from uuid import uuid4

from models import MemoryItem, Provenance, Scope

import compose as C


def _item(text, content_hash=None):
    return MemoryItem(
        item_id=uuid4(),
        source_type="user_fact",
        scope=Scope(user_id="u1"),
        text=text,
        provenance=Provenance(origin="user_explicit", writer="hook", content_hash=content_hash),
    )


def test_count_tokens_positive():
    assert C.count_tokens("") == 1
    assert C.count_tokens("hello world") >= 1


def test_basic_block():
    r = C.compose_context([(_item("fact one"), 0.9), (_item("fact two"), 0.8)], budget_tokens=1000)
    assert C.BLOCK_HEADER in r.block
    assert "- fact one" in r.block and "- fact two" in r.block
    assert len(r.items) == 2
    assert r.tokens <= 1000


def test_dedup_by_content_hash():
    r = C.compose_context(
        [(_item("dup", "h1"), 0.9), (_item("dup2", "h1"), 0.8), (_item("uniq", "h2"), 0.7)],
        budget_tokens=1000,
    )
    assert len(r.items) == 2  # العنصر الثاني (نفس h1) مُسقَط


def test_never_exceeds_budget():
    items = [(_item("x" * 200), 0.9) for _ in range(20)]
    r = C.compose_context(items, budget_tokens=60)
    assert r.tokens <= 60
    if r.block:
        assert C.count_tokens(r.block) <= 60


def test_empty_when_budget_below_header():
    r = C.compose_context([(_item("anything"), 0.9)], budget_tokens=1)
    assert r.items == [] and r.block == "" and r.tokens == 0
