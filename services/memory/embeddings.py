"""
عميل التضمين (ADR-019، M2): يطلب التضمين عبر **بوّابة LiteLLM** (موديل `embed-default`، عقد
OpenAI /v1/embeddings) ويحوّل المتجه لصيغة pgvector. الإعداد من البيئة (config-driven، R-ARCH-40).
التوجيه عبر البوّابة لا المحرّك مباشرةً (R-ARCH-10، ADR-023: كل مرور موديل عبر البوّابة — للتوسّع)؛
التبديل لمزوّد managed لاحقاً = سطر `api_base` في litellm-config فقط.
"""

from __future__ import annotations

import math
import os

import httpx

EMBEDDINGS_URL = os.environ.get("EMBEDDINGS_URL", "http://litellm:4000/v1")  # البوّابة (ADR-023)
EMBEDDINGS_API_KEY = os.environ.get("EMBEDDINGS_API_KEY", "")
EMBEDDINGS_MODEL = os.environ.get("EMBEDDINGS_MODEL", "embed-default")
EMBEDDING_MODEL_VERSION = os.environ.get("EMBEDDING_MODEL_VERSION", "qwen3-emb-0.6b-q8@1024")
# مهلة قصيرة (ADR-023): التضمين سريع (~30ms)؛ نسقط للفظي fail-soft بدل حجز worker بوّابة على المسار
# الحارّ (دون ميزانية الـ hook ~10s) — يخفّف تشبّع التزامن مع التوجيه عبر البوّابة.
EMBED_TIMEOUT = float(os.environ.get("EMBED_TIMEOUT", "8"))
# تعليمة الاستعلام لـ Qwen3 (استرجاع لا-تماثلي): الاستعلام يحمل التعليمة، المخزون (الوثائق) لا —
# يحسّن تطابق الاستعلام/الوثيقة دون إعادة تضمين (config-driven، M2 — مطابق توصية Qwen3-Embedding).
QUERY_INSTRUCTION = os.environ.get(
    "CTX_QUERY_INSTRUCTION",
    "Given a user message, retrieve stored facts and past context about the user relevant to it.",
)


def _headers(request_id: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {EMBEDDINGS_API_KEY}"} if EMBEDDINGS_API_KEY else {}
    if request_id:
        h["X-Request-ID"] = request_id  # سلسلة معرّف الطلب عبر البوّابة (R-ERR-15/19)
    return h


async def embed_one(text: str, request_id: str | None = None) -> list[float]:
    """متجه تضمين لنصّ واحد عبر بوّابة /v1/embeddings (للوثائق: بلا تعليمة استعلام)."""
    async with httpx.AsyncClient(timeout=EMBED_TIMEOUT) as c:
        r = await c.post(
            f"{EMBEDDINGS_URL}/embeddings",
            json={"model": EMBEDDINGS_MODEL, "input": text},
            headers=_headers(request_id),
        )
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]


async def embed_query(text: str, request_id: str | None = None) -> list[float]:
    """متجه تضمين **استعلام** بتعليمة Qwen3 (لا-تماثلي) — يحسّن الاسترجاع الدلالي عن embed_one."""
    return await embed_one(f"Instruct: {QUERY_INSTRUCTION}\nQuery: {text}", request_id=request_id)


def to_pgvector(vec: list[float]) -> str:
    """صيغة pgvector النصّية '[v1,v2,...]' (تُمرَّر كنص وتُحوَّل ::halfvec في SQL).
    يرفض القيم غير المنتهية (inf/nan) — تكسر cast الـ halfvec؛ الرفع يُلتقط fail-soft."""
    if not all(math.isfinite(x) for x in vec):
        raise ValueError("non-finite value in embedding vector")
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"
