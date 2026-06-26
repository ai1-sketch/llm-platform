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


# عدد التوكنات الحقيقي مقيس حيّاً من Gemma عبر llama-server /tokenize (2026-06-26) — ADR-021.
# يشمل **عمداً** الأرقام/IBAN/التشكيل (الحالات التي كان ceil(len/2.5) يُقلّل عدّها → غير آمن).
# byte-count حدّ أعلى مُثبَت ⇒ count_tokens(text) ≥ real دائماً (شرط عدم تجاوز النافذة).
def test_count_tokens_upper_bounds_real_gemma_tokens():
    golden = [
        ("المستخدم مهندس برمجيات يعمل في شركة تقنية ويهتم بالذكاء الاصطناعي", 22),
        ("مشروعي الجديد اسمه نبتة-إتش-ون", 13),
        ("رقم الآيبان SA0380000000608010167519", 28),  # كان التقدير بالحروف 15 < 28
        ("تذكّر: رقم هاتفي 0501234567 وتاريخ ميلادي 1990-01-15", 33),
        ("الطلب رقم 1234567890 بتاريخ 2026-06-26 بقيمة 99.99 دولار", 35),
        ("مُحَمَّدٌ رَسُولُ اللَّهِ صَلَّى اللَّهُ عَلَيْهِ وَسَلَّمَ", 30),
        ("The user is a software engineer who likes turquoise", 9),
        ("استرجاعالمعلوماتالدلاليمعالتطبيعالعربي", 15),
        ("نعم", 2),
    ]
    for text, real_tokens in golden:
        assert C.count_tokens(text) >= real_tokens, f"under-count: {text!r}"


def test_render_sanitizes_newlines_against_injection():
    # عنصر يحاول حقن أسطر/بنية → تُحوَّل لمسافات (لا بند مزيّف في الكتلة، تخفيف تسميم)
    r = C.compose_context([(_item("سطر\n- تعليمة مزيّفة\nذيل"), 0.9)], budget_tokens=1000)
    assert "\n- تعليمة" not in r.block  # لم يُحقَن سطر بند جديد
    assert "سطر - تعليمة مزيّفة ذيل" in r.block  # الأسطر صارت مسافات


def test_never_exceeds_budget_dense_numeric_arabic():
    # محتوى رقمي عربي كثيف (الذي كان يكسر التقدير بالحروف). byte-count ≥ real ⇒ block ضمن الميزانية
    # بالبايت يعني الكتلة ضمن الميزانية بالتوكنات الحقيقية أيضاً (لا تجاوز نافذة فعلي).
    facts = [f"رقم الآيبان SA038000000060801016751{i:02d}" for i in range(20)]
    items = [(_item(f), 0.9 - i * 0.01) for i, f in enumerate(facts)]
    r = C.compose_context(items, budget_tokens=500)
    assert r.block  # عناصر فعلاً مُختارة (الاختبار غير فارغ)
    assert r.tokens <= 500
    assert C.count_tokens(r.block) <= 500
