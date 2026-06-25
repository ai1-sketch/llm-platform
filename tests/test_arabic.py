"""اختبارات normalize_ar (ADR-019، M2) — قواعد ar-v1 + ثبات الفهرسة=الاستعلام."""

from arabic import NORMALIZE_VERSION, normalize_ar


def test_version_pinned():
    assert NORMALIZE_VERSION == "ar-v1"


def test_empty_and_none():
    assert normalize_ar("") == ""
    assert normalize_ar(None) == ""


def test_diacritics_and_tatweel_removed():
    assert normalize_ar("مَرْحَبًا") == "مرحبا"
    assert normalize_ar("كتـــاب") == "كتاب"


def test_alef_unified():
    assert normalize_ar("أحمد") == "احمد"
    assert normalize_ar("إيمان") == "ايمان"
    assert normalize_ar("آمال") == "امال"


def test_alef_maksura_and_ta_marbuta():
    assert normalize_ar("مصطفى") == "مصطفي"
    assert normalize_ar("مدرسة") == "مدرسه"


def test_idempotent_index_equals_query():
    # تطبيع المُطبَّع = المُطبَّع (شرط تطابق الفهرسة والاستعلام)
    s = "المُدرِّسةُ الأولى"
    assert normalize_ar(normalize_ar(s)) == normalize_ar(s)


def test_latin_lowercased_and_whitespace():
    assert normalize_ar("  Hello   World  ") == "hello world"
