"""
LiteLLM hook للذاكرة per-user (Context Engine) — ADR-012/013/019.
- يقرأ الهوية من X-OpenWebUI-User-Id والمحادثة من X-OpenWebUI-Chat-Id (مُثبَتان end-to-end).
- READ: يستدعي /v1/assemble (استرجاع دلالي + ترتيب + ميزانية) ويحقن كتلة السياق في رسالة system.
- WRITE (HITL): عند بادئة "تذكّر:" / "remember:" يخزّن ما بعدها (المستخدم يقرّر ما يُحفظ).
- CAPTURE (M4b، تلقائي): يلتقط الدور (المستخدم + **إجابة الموديل** content لا reasoning) وقت
  توليده — غير-streaming عبر `post_call_success_hook`، streaming عبر `streaming_iterator_hook`
  (تمرير-أولاً ثم تجميع). مهمة خلفية بلا كمون. re-entrant-safe (تضمين بلا chat-id → لا التقاط).
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
# التقاط المحادثة (M4b): الدور (مستخدم + إجابة الموديل) وقت توليده عبر hooks ما-بعد-الرد —
# post_call_success (غير-streaming) + streaming_iterator (streaming). مهمة خلفية، بلا كمون، dedup.
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


def _content_of(response):
    """نصّ **الإجابة** (message.content) من ModelResponse — نتجاهل reasoning_content (تفكير)."""
    try:
        choices = getattr(response, "choices", None)
        if not choices:
            return ""
        msg = getattr(choices[0], "message", None)
        return (getattr(msg, "content", None) or "").strip()
    except Exception:  # noqa: BLE001 — استخراج دفاعي
        return ""


def _request_ctx(data):
    """يستخرج (user_id, chat_id, user_text) من طلب البوّابة (proxy_server_request + messages)."""
    headers = (data.get("proxy_server_request") or {}).get("headers") or {}
    messages = data.get("messages") or []
    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    user_text = _text_of(last_user).strip() if last_user else ""
    return headers.get("x-openwebui-user-id"), headers.get("x-openwebui-chat-id"), user_text


class MemoryHook(CustomLogger):
    def _fire_capture(self, data, assistant_text, request_id):
        """يطلق التقاط الدور (المستخدم + إجابة الموديل) في الخلفية (بلا كمون). يُستدعى من hooks
        ما-بعد-الرد: غير-streaming من post_call_success، streaming من iterator. dedup → idempotency.
        آمن من الحلقة: نداء التضمين الداخلي بلا chat-id → لا التقاط."""
        if not CAPTURE_ENABLED:
            return
        user_id, chat_id, user_text = _request_ctx(data)
        if not (user_id and chat_id):
            return
        turns = []
        if user_text and not _is_remember(user_text):
            turns.append({"role": "user", "content": user_text})
        if assistant_text:
            turns.append({"role": "assistant", "content": assistant_text})
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

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        """M4b (غير-streaming): يلتقط الدور بعد الرد. نداءات التضمين تُتخطّى (بلا chat-id/إجابة)."""
        try:
            self._fire_capture(data, _content_of(response), (data or {}).get("litellm_call_id"))
        except Exception as e:  # noqa: BLE001 — fail-open: الالتقاط لا يكسر الرد
            _log("WARN", "CAPTURE_FAILED", f"post-call capture failed: {type(e).__name__}")
        return response

    async def async_post_call_streaming_iterator_hook(
        self, user_api_key_dict, response, request_data
    ):
        """M4b (streaming): يمرّر كل chunk **أولاً** (مسار حرج لا يُعطَّل)، يجمع نصّ الإجابة (content،
        لا reasoning) أثناء التمرير، ثم يلتقط الدور بعد اكتمال التدفّق (بلا كمون على المستخدم)."""
        parts = []
        async for chunk in response:
            try:
                c = chunk.choices[0].delta.content
                if c:
                    parts.append(c)
            except Exception:  # noqa: BLE001 — التجميع لا يعطّل التمرير أبداً
                pass
            yield chunk  # تمرير-أولاً صارم: الردّ يصل المستخدم كاملاً غير معدَّل
        try:
            rid = (request_data or {}).get("litellm_call_id")
            self._fire_capture(request_data, "".join(parts).strip(), rid)
        except Exception as e:  # noqa: BLE001 — fail-open بعد اكتمال الرد
            _log("WARN", "CAPTURE_FAILED", f"stream capture failed: {type(e).__name__}")

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
