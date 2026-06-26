"""اختبارات Rank (ADR-019، M3) — min-max، اضمحلال الحداثة، الترتيب الموزون."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import rank as R
from models import MemoryItem, Provenance, Scope


def _item(importance=0.5, confidence=1.0, created_at=None):
    return MemoryItem(
        item_id=uuid4(),
        source_type="user_fact",
        scope=Scope(user_id="u1"),
        text="x",
        provenance=Provenance(origin="user_explicit", writer="hook"),
        importance=importance,
        confidence=confidence,
        created_at=created_at,
    )


def test_minmax():
    assert R._minmax([1.0, 3.0, 5.0]) == [0.0, 0.5, 1.0]
    assert R._minmax([2.0, 2.0]) == [1.0, 1.0]  # متساوية → الصلة قصوى


def test_recency_decays_with_age():
    now = datetime.now(UTC)
    fresh = R._recency(now, now)
    half = R._recency(now - timedelta(days=R.RECENCY_HALFLIFE_DAYS), now)
    assert fresh > half
    assert abs(half - 0.5) < 0.01  # عند نصف-العمر ≈ 0.5


def test_recency_none_is_neutral():
    assert R._recency(None, datetime.now(UTC)) == 0.5


def test_empty():
    assert R.rank_items([]) == []


def test_higher_relevance_ranks_first():
    now = datetime.now(UTC)
    a, b = _item(created_at=now), _item(created_at=now)
    out = R.rank_items([(a, 0.1), (b, 0.9)], now=now)
    assert out[0][0].item_id == b.item_id


def test_importance_breaks_relevance_tie():
    now = datetime.now(UTC)
    lo = _item(importance=0.1, created_at=now)
    hi = _item(importance=0.9, created_at=now)
    out = R.rank_items([(lo, 0.5), (hi, 0.5)], now=now)  # صلة متساوية
    assert out[0][0].item_id == hi.item_id  # الأهمية ترجّح
