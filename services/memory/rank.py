"""
مرحلة Rank (ADR-019، M3): درجة **حتمية** لكل مرشّح =
    score = w_rel·Relevance + w_rec·Recency + w_imp·Importance + w_conf·Confidence
- Relevance: درجة RRF من Retrieve، مُطبَّعة min-max على مجموعة الطلب → [0,1].
- Recency: اضمحلال أُسّي من created_at (نصف-عمر قابل للضبط).
- Importance/Confidence: من أعمدة العنصر (مُحدَّدة وقت الكتابة، [0,1]) — لا LLM وقت القراءة.
الأوزان قابلة للضبط من البيئة (CTX_W_*). بلا حالة، بلا I/O، بلا LLM.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from models import MemoryItem

W_REL = float(os.environ.get("CTX_W_REL", "0.55"))
W_REC = float(os.environ.get("CTX_W_REC", "0.20"))
W_IMP = float(os.environ.get("CTX_W_IMP", "0.15"))
W_CONF = float(os.environ.get("CTX_W_CONF", "0.10"))
RECENCY_HALFLIFE_DAYS = float(os.environ.get("CTX_RECENCY_HALFLIFE_DAYS", "30"))


def _minmax(vals: list[float]) -> list[float]:
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-12:
        return [1.0] * len(vals)  # كلها متساوية → الصلة قصوى للجميع
    return [(v - lo) / (hi - lo) for v in vals]


def _recency(created_at: datetime | None, now: datetime) -> float:
    if created_at is None:
        return 0.5
    age_days = max(0.0, (now - created_at).total_seconds() / 86400.0)
    return 0.5 ** (age_days / RECENCY_HALFLIFE_DAYS)


def rank_items(
    candidates: list[tuple[MemoryItem, float]],
    now: datetime | None = None,
) -> list[tuple[MemoryItem, float]]:
    """[(MemoryItem, relevance_raw)] → [(MemoryItem, score)] مُرتّبة تنازلياً."""
    if not candidates:
        return []
    now = now or datetime.now(UTC)
    relevances = _minmax([r for _, r in candidates])
    scored: list[tuple[MemoryItem, float]] = []
    for (item, _), rel in zip(candidates, relevances, strict=True):
        rec = _recency(item.created_at, now)
        score = W_REL * rel + W_REC * rec + W_IMP * item.importance + W_CONF * item.confidence
        scored.append((item, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
