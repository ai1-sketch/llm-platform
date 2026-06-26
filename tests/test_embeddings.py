"""اختبارات عميل التضمين — to_pgvector: التنسيق + رفض القيم غير المنتهية (تكسر cast halfvec)."""

import math

import pytest
from embeddings import to_pgvector


def test_to_pgvector_format():
    assert to_pgvector([0.1, -0.2, 0.0]) == "[0.1,-0.2,0.0]"


def test_to_pgvector_rejects_non_finite():
    for bad in ([float("inf"), 0.1], [float("nan")], [1.0, -math.inf]):
        with pytest.raises(ValueError, match="non-finite"):
            to_pgvector(bad)
