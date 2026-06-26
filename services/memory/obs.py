"""
تسجيل مهيكل مشترك لخدمة `memory` (R-ERR-14): سطر JSON واحد إلى stdout، `service=memory`،
بلا أسرار/محتوى مستخدم (R-ERR-18). مصدر واحد يستورده app/retrieve (لا تكرار).
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime


def log(level: str, code: str, message: str, request_id: str | None = None, **extra) -> None:
    rec = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": level,
        "service": "memory",
        "code": code,
        "message": message,
    }
    if request_id:
        rec["request_id"] = request_id
    rec.update(extra)
    print(json.dumps(rec, ensure_ascii=False), file=sys.stdout, flush=True)
