"""اختبارات LiteLLM memory hook — منطق نقي + مسارات مُكفّأة (httpx)، بلا شبكة فعلية."""

import asyncio
import json

import memory_hook as mh


def _run(coro):
    return asyncio.run(coro)


def _install_fake_httpx(
    monkeypatch, assemble_block="", raise_exc=None, write_status=200, assemble_status=200
):
    """عميل httpx وهمي يسجّل النداءات؛ POST /assemble→context_block، POST /memories→stored.
    write_status/assemble_status يحاكيان فشل HTTP لاختبار مسارات الفشل الصاخب."""
    recorder = {"calls": []}

    class _Resp:
        def __init__(self, status, payload):
            self.status_code = status
            self._payload = payload

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            if raise_exc:
                raise raise_exc
            recorder["calls"].append(("POST", url, json, headers))
            if "/assemble" in url:
                return _Resp(
                    assemble_status, {"context_block": assemble_block, "item_count": 1, "tokens": 5}
                )
            return _Resp(write_status, {"id": 1, "stored": True})

    monkeypatch.setattr(mh.httpx, "AsyncClient", _Client)
    return recorder


# ── منطق نقي ──
def test_text_of_string():
    assert mh._text_of({"content": "hi"}) == "hi"


def test_text_of_multimodal():
    msg = {
        "content": [
            {"type": "text", "text": "a"},
            {"type": "image_url"},
            {"type": "text", "text": "b"},
        ]
    }
    assert mh._text_of(msg) == "a  b"


def test_text_of_empty():
    assert mh._text_of(None) == ""
    assert mh._text_of({}) == ""


def test_log_json_shape(capsys):
    mh._log("INFO", "X_CODE", "hello", request_id="r1", extra1="v")
    rec = json.loads(capsys.readouterr().out.strip())
    assert rec["level"] == "INFO"
    assert rec["service"] == "litellm"
    assert rec["code"] == "X_CODE"
    assert rec["message"] == "hello"
    assert rec["request_id"] == "r1"
    assert rec["extra1"] == "v"
    assert "timestamp" in rec


# ── async_pre_call_hook ──
def test_hook_write_and_read(monkeypatch):
    rec = _install_fake_httpx(monkeypatch, assemble_block="سياق محفوظ: fact1")
    data = {
        "litellm_call_id": "rid-1",
        "proxy_server_request": {"headers": {"x-openwebui-user-id": "u1"}},
        "messages": [{"role": "user", "content": "تذكّر: لوني أزرق"}],
    }
    out = _run(mh.MemoryHook().async_pre_call_hook(None, None, data, "completion"))
    urls = [c[1] for c in rec["calls"]]
    assert any("/v1/memories" in u for u in urls)  # كتابة الحقيقة
    assert any("/v1/assemble" in u for u in urls)  # قراءة عبر assemble
    write = next(c for c in rec["calls"] if "/v1/memories" in c[1])
    assert write[2] == {"user_id": "u1", "content": "لوني أزرق"}  # الحقيقة بعد البادئة
    assert write[3] == {"X-Request-ID": "rid-1"}  # request_id مُمرَّر
    assert out["messages"][0]["role"] == "system"
    assert "fact1" in out["messages"][0]["content"]  # كتلة assemble حُقنت


def test_hook_read_only_no_write(monkeypatch):
    rec = _install_fake_httpx(monkeypatch, assemble_block="سياق محفوظ: fav")
    data = {
        "litellm_call_id": "rid-2",
        "proxy_server_request": {"headers": {"x-openwebui-user-id": "u1"}},
        "messages": [{"role": "user", "content": "ما لوني؟"}],
    }
    out = _run(mh.MemoryHook().async_pre_call_hook(None, None, data, "completion"))
    urls = [c[1] for c in rec["calls"]]
    assert not any("/v1/memories" in u for u in urls)  # لا كتابة (لا بادئة)
    assert any("/v1/assemble" in u for u in urls)  # قراءة فقط
    assert "fav" in out["messages"][0]["content"]


def test_hook_no_identity_passthrough(monkeypatch):
    rec = _install_fake_httpx(monkeypatch)
    data = {
        "litellm_call_id": "r",
        "proxy_server_request": {"headers": {}},
        "messages": [{"role": "user", "content": "hi"}],
    }
    out = _run(mh.MemoryHook().async_pre_call_hook(None, None, data, "completion"))
    assert rec["calls"] == []  # بلا هوية → لا نداء ذاكرة
    assert out == data


def test_hook_write_failure_logged(monkeypatch, capsys):
    # فشل حفظ "تذكّر:" يجب ألّا يُبتلَع صامتاً (R-ERR-10/21)
    _install_fake_httpx(monkeypatch, write_status=500)
    data = {
        "litellm_call_id": "rid-w5",
        "proxy_server_request": {"headers": {"x-openwebui-user-id": "u1"}},
        "messages": [{"role": "user", "content": "تذكّر: حقيقة مهمة"}],
    }
    _run(mh.MemoryHook().async_pre_call_hook(None, None, data, "completion"))
    assert "MEMORY_WRITE_FAILED" in capsys.readouterr().out


def test_hook_assemble_non_200_logged(monkeypatch, capsys):
    # assemble يفشل → لا حقن لكن سجلّ صاخب، والمحادثة لا تنكسر
    _install_fake_httpx(monkeypatch, assemble_block="سياق", assemble_status=503)
    data = {
        "litellm_call_id": "rid-a5",
        "proxy_server_request": {"headers": {"x-openwebui-user-id": "u1"}},
        "messages": [{"role": "user", "content": "ما لوني؟"}],
    }
    out = _run(mh.MemoryHook().async_pre_call_hook(None, None, data, "completion"))
    assert "ASSEMBLE_NON_200" in capsys.readouterr().out
    assert out["messages"][0]["content"] == "ما لوني؟"  # لا حقن، المحادثة سليمة


def test_hook_fail_open(monkeypatch, capsys):
    _install_fake_httpx(monkeypatch, raise_exc=mh.httpx.HTTPError("down"))
    data = {
        "litellm_call_id": "r3",
        "proxy_server_request": {"headers": {"x-openwebui-user-id": "u1"}},
        "messages": [{"role": "user", "content": "hi"}],
    }
    out = _run(mh.MemoryHook().async_pre_call_hook(None, None, data, "completion"))
    assert out["messages"] == [{"role": "user", "content": "hi"}]  # المحادثة لم تنكسر
    assert "MEMORY_BACKEND_UNAVAILABLE" in capsys.readouterr().out  # فشل صاخب مهيكل


# ── رصد per-request ──
def test_hook_budget_is_window_aware(monkeypatch):
    rec = _install_fake_httpx(monkeypatch, assemble_block="ctx")
    data = {
        "litellm_call_id": "rid-w",
        "proxy_server_request": {"headers": {"x-openwebui-user-id": "u1"}},
        "messages": [{"role": "user", "content": "ما لوني؟"}],
    }
    _run(mh.MemoryHook().async_pre_call_hook(None, None, data, "completion"))
    assemble = next(c for c in rec["calls"] if "/v1/assemble" in c[1])
    expected = min(mh.INJECTION_BUDGET, mh.MODEL_WINDOW - mh.RESERVED_TOKENS)
    assert assemble[2]["budget_tokens"] == expected
    # الثابت الأمني: المحقون + المحجوز لا يتجاوزان النافذة أبداً (ADR-021)
    assert assemble[2]["budget_tokens"] + mh.RESERVED_TOKENS <= mh.MODEL_WINDOW


def test_hook_skips_injection_when_budget_nonpositive(monkeypatch, capsys):
    monkeypatch.setattr(mh, "MODEL_WINDOW", 1000)
    monkeypatch.setattr(mh, "RESERVED_TOKENS", 1200)  # المحجوز > النافذة → budget ≤ 0
    rec = _install_fake_httpx(monkeypatch, assemble_block="ctx")
    data = {
        "litellm_call_id": "rid-z",
        "proxy_server_request": {"headers": {"x-openwebui-user-id": "u1"}},
        "messages": [{"role": "user", "content": "ما لوني؟"}],
    }
    out = _run(mh.MemoryHook().async_pre_call_hook(None, None, data, "completion"))
    assert not any("/v1/assemble" in c[1] for c in rec["calls"])  # لا محاولة حقن
    assert "INJECTION_BUDGET_NONPOSITIVE" in capsys.readouterr().out  # صاخب
    assert out["messages"][0]["content"] == "ما لوني؟"  # المحادثة لم تنكسر


# ── M4b: التقاط المحادثة (من التاريخ، مهمة خلفية في pre_call) ──
def _run_drain(hook_coro):
    """يشغّل الـ hook ثم يستنزف مهام الالتقاط الخلفية في نفس الحلقة (لاختبار create_task)."""

    async def _s():
        r = await hook_coro
        if mh._BG_TASKS:
            await asyncio.gather(*list(mh._BG_TASKS))
        return r

    return asyncio.run(_s())


def test_recent_turns_user_and_prev_assistant():
    msgs = [
        {"role": "user", "content": "س١"},
        {"role": "assistant", "content": "ج١"},
        {"role": "user", "content": "س٢"},
    ]
    assert mh._recent_turns(msgs) == [
        {"role": "user", "content": "س٢"},  # آخر دور مستخدم
        {"role": "assistant", "content": "ج١"},  # آخر دور مساعد (السابق)
    ]


def test_recent_turns_skips_remember_user():
    msgs = [{"role": "assistant", "content": "ج"}, {"role": "user", "content": "تذكّر: x"}]
    assert mh._recent_turns(msgs) == [{"role": "assistant", "content": "ج"}]  # تذكّر يُتخطّى


def test_hook_fires_capture_from_history(monkeypatch):
    rec = _install_fake_httpx(monkeypatch, assemble_block="ctx")
    mh._BG_TASKS.clear()
    data = {
        "litellm_call_id": "h1",
        "proxy_server_request": {
            "headers": {"x-openwebui-user-id": "u1", "x-openwebui-chat-id": "chat-1"}
        },
        "messages": [
            {"role": "user", "content": "أنا أحب القهوة"},
            {"role": "assistant", "content": "القهوة رائعة"},
            {"role": "user", "content": "وماذا عن الشاي؟"},
        ],
    }
    _run_drain(mh.MemoryHook().async_pre_call_hook(None, None, data, "completion"))
    cap = next(c for c in rec["calls"] if "/v1/conversation/capture" in c[1])
    body = cap[2]
    assert body["user_id"] == "u1" and body["conversation_id"] == "chat-1"
    contents = {t["role"]: t["content"] for t in body["turns"]}
    assert contents["user"] == "وماذا عن الشاي؟"  # آخر دور مستخدم
    assert contents["assistant"] == "القهوة رائعة"  # دور المساعد السابق (من التاريخ)


def test_hook_no_capture_without_chat_id(monkeypatch):
    rec = _install_fake_httpx(monkeypatch, assemble_block="ctx")
    mh._BG_TASKS.clear()
    data = {
        "litellm_call_id": "h2",
        "proxy_server_request": {"headers": {"x-openwebui-user-id": "u1"}},
        "messages": [{"role": "user", "content": "hi"}],
    }
    _run_drain(mh.MemoryHook().async_pre_call_hook(None, None, data, "completion"))
    assert not any("/v1/conversation/capture" in c[1] for c in rec["calls"])


def test_hook_no_capture_when_disabled(monkeypatch):
    monkeypatch.setattr(mh, "CAPTURE_ENABLED", False)
    rec = _install_fake_httpx(monkeypatch, assemble_block="ctx")
    mh._BG_TASKS.clear()
    data = {
        "litellm_call_id": "h3",
        "proxy_server_request": {
            "headers": {"x-openwebui-user-id": "u1", "x-openwebui-chat-id": "c"}
        },
        "messages": [{"role": "user", "content": "hi"}],
    }
    _run_drain(mh.MemoryHook().async_pre_call_hook(None, None, data, "completion"))
    assert not any("/v1/conversation/capture" in c[1] for c in rec["calls"])


def test_success_event_cost_log(capsys):
    kwargs = {
        "standard_logging_object": {
            "litellm_call_id": "rid-9",
            "response_cost": 0.0,
            "total_tokens": 42,
            "model": "Gemma 4",
            "status": "success",
        }
    }
    _run(mh.MemoryHook().async_log_success_event(kwargs, None, None, None))
    rec = json.loads(capsys.readouterr().out.strip())
    assert rec["code"] == "REQUEST_COMPLETED"
    assert rec["request_id"] == "rid-9"
    assert rec["response_cost"] == 0.0
    assert rec["total_tokens"] == 42
