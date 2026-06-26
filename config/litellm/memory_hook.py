"""
LiteLLM hook للذاكرة per-user (L1) — ADR-012/013.
- يقرأ هوية المستخدم من X-OpenWebUI-User-Id (مُثبَت end-to-end).
- READ: يستدعي /v1/assemble (استرجاع دلالي + ترتيب + ميزانية) ويحقن كتلة السياق في رسالة system.
- WRITE (HITL): عند بادئة "تذكّر:" / "remember:" يخزّن ما بعدها (المستخدم يقرّر ما يُحفظ).
- fail-open: أي خطأ في الذاكرة لا يكسر المحادثة — لكنه يُسجَّل **بصوت** كسطر JSON مهيكل (R-ERR-08/14).
- رصد (P-05): سطر JSON بالكلفة + request_id لكل طلب (success/failure event، R-ERR-15/16).
  request_id = litellm_call_id (يُضبط في البوّابة قبل الـ hook ويطابق standard_logging_object).
"""

import json
import os
import sys
from datetime import UTC, datetime

import httpx
from litellm.integrations.custom_logger import CustomLogger

MEM_URL = "http://memory:8088"
REMEMBER_PREFIXES = ("تذكّر:", "تذكر:", "remember:", "/remember ")
SERVICE = "litellm"  # هذا الكود يعمل داخل عملية البوّابة → service يطابق اسم خدمة Docker (R-ARCH-34)
INJECTION_BUDGET = int(
    os.environ.get("CTX_INJECTION_BUDGET", "1000")
)  # ميزانية حقن الذاكرة (توكنات، config-driven)


def _log(level, code, message, request_id=None, **extra):
    """سطر سجل JSON واحد إلى stdout (R-ERR-14). لا يطبع محتوى المستخدم أو الأسرار (R-ERR-18)."""
    rec = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": level,
        "service": SERVICE,
        "code": code,
        "message": message,
    }
    if request_id:
        rec["request_id"] = request_id
    rec.update(extra)
    print(json.dumps(rec, ensure_ascii=False), file=sys.stdout, flush=True)


def _text_of(msg):
    c = msg.get("content") if msg else ""
    if isinstance(c, list):  # محتوى multimodal
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    return c or ""


class MemoryHook(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        request_id = data.get("litellm_call_id")  # مُضبَط في البوّابة قبل هذا الـ hook
        headers_out = {"X-Request-ID": request_id} if request_id else {}
        try:
            headers = (data.get("proxy_server_request") or {}).get("headers") or {}
            user_id = headers.get("x-openwebui-user-id")
            messages = data.get("messages") or []
            if not user_id or not messages:
                return data

            last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
            text = _text_of(last_user).strip()

            # WRITE (HITL صريح)
            for p in REMEMBER_PREFIXES:
                if text.lower().startswith(p.lower()):
                    fact = text[len(p) :].strip()
                    if fact:
                        async with httpx.AsyncClient(timeout=5) as c:
                            await c.post(
                                f"{MEM_URL}/v1/memories",
                                json={"user_id": user_id, "content": fact},
                                headers=headers_out,
                            )
                    break

            # READ عبر /v1/assemble: استرجاع دلالي + ترتيب + ميزانية (M3/M4) → كتلة مُسيَّجة جاهزة
            if text:
                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.post(
                        f"{MEM_URL}/v1/assemble",
                        json={"user_id": user_id, "query": text, "budget_tokens": INJECTION_BUDGET},
                        headers=headers_out,
                    )
                block = r.json().get("context_block", "") if r.status_code == 200 else ""
                if block:
                    if messages and messages[0].get("role") == "system":
                        messages[0]["content"] = _text_of(messages[0]) + "\n\n" + block
                    else:
                        messages.insert(0, {"role": "system", "content": block})
                    data["messages"] = messages
        except httpx.HTTPError as e:
            # فشل متوقّع في الاتصال بخدمة الذاكرة → fail-open لكن صاخب ومهيكل
            _log(
                "ERROR",
                "MEMORY_BACKEND_UNAVAILABLE",
                f"memory backend call failed: {type(e).__name__}",
                request_id,
            )
        except Exception as e:  # noqa: BLE001 — fail-open مقصود للذاكرة؛ نسجّله بـ code ولا نبتلعه صامتاً
            _log(
                "ERROR",
                "MEMORY_HOOK_FAILED",
                f"unexpected memory-hook error: {type(e).__name__}",
                request_id,
            )
        return data

    # ── رصد per-request (P-05): كلفة + request_id لكل طلب (R-ERR-15/16) ──
    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            slo = kwargs.get("standard_logging_object") or {}
            request_id = slo.get("litellm_call_id") or kwargs.get("litellm_call_id")
            cost = slo.get("response_cost")
            if cost is None:
                cost = kwargs.get("response_cost")
            _log(
                "INFO",
                "REQUEST_COMPLETED",
                f"completion ok model={slo.get('model')}",
                request_id=request_id,
                response_cost=cost,
                total_tokens=slo.get("total_tokens"),
                status=slo.get("status"),
            )
        except Exception as e:  # noqa: BLE001 — الرصد لا يجب أن يكسر الطلب
            _log("WARN", "COST_LOG_FAILED", f"could not emit cost log: {type(e).__name__}")

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        try:
            slo = kwargs.get("standard_logging_object") or {}
            request_id = slo.get("litellm_call_id") or kwargs.get("litellm_call_id")
            _log(
                "ERROR",
                "REQUEST_FAILED",
                f"completion failed model={slo.get('model')}: {slo.get('error_str')}",
                request_id=request_id,
                response_cost=slo.get("response_cost"),
                status=slo.get("status"),
            )
        except Exception as e:  # noqa: BLE001 — الرصد لا يجب أن يكسر الطلب
            _log("WARN", "FAILURE_LOG_FAILED", f"could not emit failure log: {type(e).__name__}")


proxy_handler_instance = MemoryHook()
