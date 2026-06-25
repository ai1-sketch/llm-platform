"""
LiteLLM hook للذاكرة per-user (L1) — ADR-012.
- يقرأ هوية المستخدم من X-OpenWebUI-User-Id (مُثبَت end-to-end).
- READ: يجيب ذاكرة المستخدم من خدمة memory ويحقنها في رسالة system.
- WRITE (HITL): عند بادئة "تذكّر:" / "remember:" يخزّن ما بعدها (المستخدم يقرّر ما يُحفظ).
- fail-open: أي خطأ في الذاكرة لا يكسر المحادثة (يُسجَّل فقط).
"""
import httpx
from litellm.integrations.custom_logger import CustomLogger

MEM_URL = "http://memory:8088"
REMEMBER_PREFIXES = ("تذكّر:", "تذكر:", "remember:", "/remember ")
MAX_FACTS = 20


def _text_of(msg):
    c = msg.get("content") if msg else ""
    if isinstance(c, list):  # محتوى multimodal
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    return c or ""


class MemoryHook(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
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
                    fact = text[len(p):].strip()
                    if fact:
                        async with httpx.AsyncClient(timeout=5) as c:
                            await c.post(f"{MEM_URL}/v1/memories",
                                         json={"user_id": user_id, "content": fact})
                    break

            # READ + حقن
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(f"{MEM_URL}/v1/memories",
                                params={"user_id": user_id, "limit": MAX_FACTS})
            mems = r.json().get("memories", []) if r.status_code == 200 else []
            if mems:
                facts = "\n".join(f"- {m['content']}" for m in mems[:MAX_FACTS])
                mem_text = ("معلومات محفوظة عن هذا المستخدم (استخدمها عند الحاجة، "
                            "ولا تذكر أنها 'ذاكرة' إلا إذا سُئلت):\n" + facts)
                if messages and messages[0].get("role") == "system":
                    messages[0]["content"] = _text_of(messages[0]) + "\n\n" + mem_text
                else:
                    messages.insert(0, {"role": "system", "content": mem_text})
                data["messages"] = messages
        except Exception as e:  # fail-open: لا نكسر المحادثة بسبب الذاكرة
            print(f"[memory-hook] error: {e}", flush=True)
        return data


proxy_handler_instance = MemoryHook()
