"""
LiteLLM hook للذاكرة per-user (Context Engine) — ADR-012/013/019.
- يقرأ الهوية من X-OpenWebUI-User-Id والمحادثة من X-OpenWebUI-Chat-Id (مُثبَتان end-to-end).
- READ: يستدعي /v1/assemble (استرجاع دلالي + ترتيب + ميزانية) ويحقن كتلة السياق في رسالة system.
- WRITE (HITL): عند بادئة "تذكّر:" / "remember:" يخزّن ما بعدها (المستخدم يقرّر ما يُحفظ).
- CAPTURE (M4b، تلقائي): بعد الرد (بلا كمون) يلتقط دور المستخدم في conversation_memory عبر جسر
  pre_call→log_success؛ دور المساعد لغير-streaming فقط (streaming = v2). re-entrant-safe.
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
# ميزانية حقن واعية بالنافذة (ADR-021): config-driven، fail-open.
# الفعلية = min(INJECTION_BUDGET, MODEL_WINDOW - RESERVED_TOKENS) ⇒ injected+reserved ≤ window.
INJECTION_BUDGET = int(os.environ.get("CTX_INJECTION_BUDGET", "1000"))  # سقف الحقن المرغوب
MODEL_WINDOW = int(os.environ.get("CTX_MODEL_WINDOW", "4096"))  # نافذة الموديل (حدّثها عند تبديله)
RESERVED_TOKENS = int(os.environ.get("CTX_RESERVED_TOKENS", "2560"))  # محجوز للجواب + الرسائل الحيّة
# التقاط المحادثة (M4b): جسر pre_call→log_success (post-response، بلا كمون) call_id → سياق الدور.
CAPTURE_ENABLED = os.environ.get("CTX_CAPTURE_CONVERSATION", "true").lower() == "true"
_PENDING: dict[str, dict] = {}


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


def _is_remember(text):
    return any(text.lower().startswith(p.lower()) for p in REMEMBER_PREFIXES)


def _assistant_text(obj):
    """نصّ جواب المساعد من ModelResponse/dict/str — يغطّي streaming وغير-streaming؛ دفاعي."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj.strip()
    try:
        choices = obj.get("choices") if isinstance(obj, dict) else getattr(obj, "choices", None)
        if not choices:
            return ""
        first = choices[0]
        msg = first.get("message") if isinstance(first, dict) else getattr(first, "message", None)
        if msg is None:  # بديل streaming: delta
            msg = first.get("delta") if isinstance(first, dict) else getattr(first, "delta", None)
        content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
        return (content or "").strip()
    except Exception:  # noqa: BLE001 — استخراج دفاعي
        return ""


class MemoryHook(CustomLogger):
    def _stash_for_capture(self, user_id, headers, text, request_id):
        """يخزّن سياق الدور (M4b) ليلتقطه log_success بعد الرد بلا كمون. يتخطّى أوامر 'تذكّر:'."""
        if not (CAPTURE_ENABLED and request_id):
            return
        chat_id = headers.get("x-openwebui-chat-id")
        if not chat_id or _is_remember(text):
            return
        if len(_PENDING) > 5000:  # حارس تسرّب دفاعي (يُفرَّغ عادةً في success/failure)
            _PENDING.clear()
        _PENDING[request_id] = {"user_id": user_id, "conversation_id": chat_id, "user_text": text}

    async def _capture_turns(self, request_id, assistant_text):
        """التقاط دور المستخدم + جواب المساعد في conversation_memory (post-response). آمن من الحلقة:
        نداء التضمين الداخلي لا يُخزَّن في _PENDING (بلا user_id في pre_call)."""
        pend = _PENDING.pop(request_id, None) if request_id else None
        if not pend:
            return
        turns = [{"role": "user", "content": pend["user_text"]}]
        if assistant_text:
            turns.append({"role": "assistant", "content": assistant_text})
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(
                f"{MEM_URL}/v1/conversation/capture",
                json={
                    "user_id": pend["user_id"],
                    "conversation_id": pend["conversation_id"],
                    "turns": turns,
                },
                headers={"X-Request-ID": request_id} if request_id else {},
            )

    async def _maybe_write(self, user_id, text, headers_out, request_id):
        """WRITE (HITL صريح): يخزّن ما بعد بادئة 'تذكّر:'/'remember:' فقط (المستخدم يقرّر)."""
        for p in REMEMBER_PREFIXES:
            if text.lower().startswith(p.lower()):
                fact = text[len(p) :].strip()
                if fact:
                    async with httpx.AsyncClient(timeout=5) as c:
                        r = await c.post(
                            f"{MEM_URL}/v1/memories",
                            json={"user_id": user_id, "content": fact},
                            headers=headers_out,
                        )
                    if r.status_code >= 300:  # لا نبتلع فشل الحفظ صامتاً (R-ERR-10/21)
                        _log(
                            "ERROR",
                            "MEMORY_WRITE_FAILED",
                            f"store 'remember' fact failed: HTTP {r.status_code}",
                            request_id,
                        )
                return

    async def _assemble_and_inject(self, user_id, text, messages, data, headers_out, request_id):
        """READ: ميزانية واعية بالنافذة (ADR-021) → حقن كتلة السياق في رسالة system."""
        budget = min(INJECTION_BUDGET, MODEL_WINDOW - RESERVED_TOKENS)
        if budget <= 0:  # النافذة مستهلَكة بالكامل بالمحجوز → لا حقن (fail-open، لكن صاخب)
            _log(
                "WARN",
                "INJECTION_BUDGET_NONPOSITIVE",
                f"window={MODEL_WINDOW} reserved={RESERVED_TOKENS} -> skip injection",
                request_id,
            )
            return
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{MEM_URL}/v1/assemble",
                json={"user_id": user_id, "query": text, "budget_tokens": budget},
                headers=headers_out,
            )
        if r.status_code != 200:  # فشل assemble → لا حقن، لكن صاخب (لا ابتلاع صامت، R-ERR-10)
            _log(
                "WARN",
                "ASSEMBLE_NON_200",
                f"assemble returned HTTP {r.status_code}; no context injected",
                request_id,
            )
            return
        block = r.json().get("context_block", "")
        if not block:
            return
        if messages[0].get("role") == "system":
            messages[0]["content"] = _text_of(messages[0]) + "\n\n" + block
        else:
            messages.insert(0, {"role": "system", "content": block})
        data["messages"] = messages

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
            if not text:
                return data
            self._stash_for_capture(user_id, headers, text, request_id)  # M4b (يُلتقَط post-response)
            await self._maybe_write(user_id, text, headers_out, request_id)
            await self._assemble_and_inject(user_id, text, messages, data, headers_out, request_id)
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
        slo = kwargs.get("standard_logging_object") or {}
        request_id = slo.get("litellm_call_id") or kwargs.get("litellm_call_id")
        try:
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
        # M4b: التقاط المحادثة بعد الرد (بلا كمون). دور المستخدم دائماً؛
        # دور المساعد لغير-streaming فقط (streaming/OWUI عبر iterator-hook = مؤجَّل v2).
        try:
            assistant_text = _assistant_text(response_obj) or _assistant_text(slo.get("response"))
            await self._capture_turns(request_id, assistant_text)
        except Exception as e:  # noqa: BLE001 — fail-open: الالتقاط لا يكسر شيئاً
            if request_id:
                _PENDING.pop(request_id, None)
            _log(
                "WARN",
                "CAPTURE_FAILED",
                f"conversation capture failed: {type(e).__name__}",
                request_id,
            )

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        try:
            slo = kwargs.get("standard_logging_object") or {}
            request_id = slo.get("litellm_call_id") or kwargs.get("litellm_call_id")
            if request_id:
                _PENDING.pop(request_id, None)  # M4b: تنظيف الجسر للطلبات الفاشلة (لا التقاط)
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
