"""
تطبيع عربي مشترك (ADR-019، M2) — دالة واحدة `normalize_ar` تُستخدم **وقت الفهرسة ووقت الاستعلام**
بشكل متطابق (شرط دقّة الاسترجاع اللفظي). مُصدَّرة بإصدار (`NORMALIZE_VERSION`) لأي تغيير لاحق.

سياسة ar-v1 (مُجمَّدة): NFKC · إزالة التطويل · إزالة التشكيل (الحركات) · توحيد الألف (آأإٱ→ا) ·
الألف المقصورة (ى→ي) · التاء المربوطة (ة→ه) · تصغير اللاتيني · ضغط الفراغات.
لا نمسّ مقاعد الهمزة (ؤ/ئ) في v1 (تجنّب الإفراط؛ قرار مُجمَّد).
"""

from __future__ import annotations

import re
import unicodedata

NORMALIZE_VERSION = "ar-v1"

_TATWEEL = "ـ"  # ـ
# التشكيل/العلامات (escapes صريحة): علامات عربية + حركات/تنوين + ألف خنجرية + تعليقات قرآنية
_DIACRITICS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭ]")
_ALEF = re.compile("[آأإٱ]")  # آ أ إ ٱ → ا
_ALEF_MAKSURA = "ى"  # ى
_YA = "ي"  # ي
_TA_MARBUTA = "ة"  # ة
_HA = "ه"  # ه
_WS = re.compile(r"\s+")


def normalize_ar(text: str | None) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = t.replace(_TATWEEL, "")
    t = _DIACRITICS.sub("", t)
    t = _ALEF.sub("ا", t)
    t = t.replace(_ALEF_MAKSURA, _YA)
    t = t.replace(_TA_MARBUTA, _HA)
    t = t.lower()
    return _WS.sub(" ", t).strip()
