"""
LiteLLM hook للذاكرة per-user (Context Engine) — ADR-012/013/019.
- يقرأ الهوية من X-OpenWebUI-User-Id والمحادثة من X-OpenWebUI-Chat-Id (مُثبَتان end-to-end).
- READ: يستدعي /v1/assemble (استرجاع دلالي + ترتيب + ميزانية) ويحقن كتلة السياق في رسالة system.
- WRITE (HITL): عند بادئة "تذكّر:" / "remember:" يخزّن ما بعدها (المستخدم يقرّر ما يُحفظ).
- CAPTURE (M4b، تلقائي): مهمة خلفية في pre_call (بلا كمون) تلتقط من **تاريخ الرسائل** دورَ المستخدم
  الحالي + دورَ المساعد السابق في conversation_memory — يعمل streaming وغير-streaming (التاريخ مصدر
  موثوق مستقلّ عن التسليم؛ آخر دور مساعد في محادثة مهجورة يُلتقَط عند الاستئناف). re-entrant-safe.
- fail-open: أي خطأ في الذاكرة لا يكسر المحادثة — لكنه يُسجَّل **بصوت** كسطر JSON مهيكل (R-ERR-08/14).
- رصد (P-05): سطر JSON بالكلفة + request_id لكل طلب (success/failure event، R-ERR-15/16).
  request_id = litellm_call_id (يُضبط في البوّابة قبل الـ hook ويطابق standard_logging_object).
"""

import asyncio
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
# التقاط المحادثة (M4b): من **تاريخ الرسائل** في pre_call (مهمة خلفية، بلا كمون) — مستقلّ عن نمط
# التسليم (streaming/غير)؛ يلتقط دور المستخدم الحالي + دور المساعد السابق. dedup يضمن idempotency.
CAPTURE_ENABLED = os.environ.get("CTX_CAPTURE_CONVERSATION", "true").lower() == "true"
_BG_TASKS: set = set()  # مراجع مهام الالتقاط الخلفية (يمنع جمع القمامة قبل اكتمالها)


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


def _recent_turns(messages):
    """آخر دور مستخدم (غير 'تذكّر:') + آخر دور مساعد من تاريخ المحادثة — للالتقاط idempotent.
    التاريخ مصدر موثوق مستقلّ عن نمط التسليم (يحوي ردود المساعد السابقة كاملةً، عكس deltas)."""
    turns = []
    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    last_assistant = next((m for m in reversed(messages) if m.get("role") == "assistant"), None)
    if last_user:
        tu = _text_of(last_user).strip()
        if tu and not _is_remember(tu):
            turns.append({"role": "user", "content": tu})
    if last_assistant:
        ta = _text_of(last_assistant).strip()
        if ta:
            turns.append({"role": "assistant", "content": ta})
    return turns


class MemoryHook(CustomLogger):
    def _fire_capture(self, user_id, headers, messages, request_id):
        """يطلق التقاط المحادثة في الخلفية (بلا كمون على المستخدم) من تاريخ الرسائل: دور المستخدم
        الحالي + دور المساعد السابق. يعمل streaming وغير-streaming (التاريخ مستقلّ عن التسليم).
        آمن من الحلقة: نداء التضمين الداخلي بلا chat-id في pre_call → لا التقاط."""
        if not CAPTURE_ENABLED:
            return
        chat_id = headers.get("x-openwebui-chat-id")
        if not chat_id:
            return
        turns = _recent_turns(messages)
        if not turns:
            return
        task = asyncio.create_task(self._do_capture(user_id, chat_id, turns, request_id))
        _BG_TASKS.add(task)  # مرجع يمنع GC؛ يُزال عند الاكتمال
        task.add_done_callback(_BG_TASKS.discard)

    async def _do_capture(self, user_id, conversation_id, turns, request_id):
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(
                    f"{MEM_URL}/v1/conversation/capture",
                    json={"user_id": user_id, "conversation_id": conversation_id, "turns": turns},
                    headers={"X-Request-ID": request_id} if request_id else {},
                )
        except Exception as e:  # noqa: BLE001 — fail-open: الالتقاط لا يكسر شيئاً
            _log("WARN", "CAPTURE_FAILED", f"capture failed: {type(e).__name__}", request_id)

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
            self._fire_capture(user_id, headers, messages, request_id)  # M4b (خلفي)
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
