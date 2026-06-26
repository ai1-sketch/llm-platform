"""
إعداد الاختبارات (ADR-008). نُكفّئ التبعيات الثقيلة/المُصرَّفة (litellm, asyncpg) كي تُختبَر
منطقتنا بلا تثبيتها، ونضيف مجلّدي الكود للـ path. الاختبارات لا تلمس قاعدة بيانات حقيقية.
"""

import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "config" / "litellm"))
sys.path.insert(0, str(ROOT / "services" / "memory"))

# stub litellm: الـ hook يرث CustomLogger فقط
_litellm = types.ModuleType("litellm")
_integrations = types.ModuleType("litellm.integrations")
_custom = types.ModuleType("litellm.integrations.custom_logger")


class _CustomLogger:
    def __init__(self, *a, **k):
        pass


_custom.CustomLogger = _CustomLogger
sys.modules.setdefault("litellm", _litellm)
sys.modules.setdefault("litellm.integrations", _integrations)
sys.modules.setdefault("litellm.integrations.custom_logger", _custom)

# نُكفّئ asyncpg **فقط إن لم يكن مُثبَّتاً** (اختبارات الوحدة بلا DB تحقن mock pool).
# إن توفّر asyncpg الحقيقي (بيئة التكامل/CI) نستخدمه كما هو ليعمل اختبار العزل على Postgres حقيقي.
try:
    import asyncpg  # noqa: F401
except ImportError:
    _asyncpg = types.ModuleType("asyncpg")
    _asyncpg.Pool = object

    async def _create_pool(*a, **k):
        return MagicMock()

    _asyncpg.create_pool = _create_pool
    sys.modules["asyncpg"] = _asyncpg

# app.py يفشل-بسرعة إن غاب MEMORY_DATABASE_URL → نضبطه قبل الاستيراد
os.environ.setdefault("MEMORY_DATABASE_URL", "postgresql://test:test@localhost/test")
