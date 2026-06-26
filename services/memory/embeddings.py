"""
عميل التضمين (ADR-019، M2): يطلب التضمين عبر **بوّابة LiteLLM** (موديل `embed-default`، عقد
OpenAI /v1/embeddings) ويحوّل المتجه لصيغة pgvector. الإعداد من البيئة (config-driven، R-ARCH-40).
التوجيه عبر البوّابة لا المحرّك مباشرةً (R-ARCH-10، ADR-023: كل مرور موديل عبر البوّابة — للتوسّع)؛
التبديل لمزوّد managed لاحقاً = سطر `api_base` في litellm-config فقط.
"""

from __future__ import annotations

import os

import httpx

EMBEDDINGS_URL = os.environ.get("EMBEDDINGS_URL", "http://litellm:4000/v1")  # البوّابة (ADR-023)
EMBEDDINGS_API_KEY = os.environ.get("EMBEDDINGS_API_KEY", "")
EMBEDDINGS_MODEL = os.environ.get("EMBEDDINGS_MODEL", "embed-default")
EMBEDDING_MODEL_VERSION = os.environ.get("EMBEDDING_MODEL_VERSION", "qwen3-emb-0.6b-q8@1024")
# مهلة قصيرة (ADR-023): التضمين سريع (~30ms)؛ نسقط للفظي fail-soft بدل حجز worker بوّابة على المسار
# الحارّ (دون ميزانية الـ hook ~10s) — يخفّف تشبّع التزامن مع التوجيه عبر البوّابة.
EMBED_TIMEOUT = float(os.environ.get("EMBED_TIMEOUT", "8"))


def _headers() -> dict:
    return {"Authorization": f"Bearer {EMBEDDINGS_API_KEY}"} if EMBEDDINGS_API_KEY else {}


async def embed_one(text: str) -> list[float]:
    """متجه تضمين لنصّ واحد عبر عقد OpenAI /v1/embeddings."""
    async with httpx.AsyncClient(timeout=EMBED_TIMEOUT) as c:
        r = await c.post(
            f"{EMBEDDINGS_URL}/embeddings",
            json={"model": EMBEDDINGS_MODEL, "input": text},
            headers=_headers(),
        )
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]


def to_pgvector(vec: list[float]) -> str:
    """صيغة pgvector النصّية '[v1,v2,...]' (تُمرَّر كنص وتُحوَّل ::halfvec في SQL)."""
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"
