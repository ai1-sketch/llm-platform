"""اختبارات LiteLLM memory hook — منطق نقي + مسارات مُكفّأة (httpx)، بلا شبكة فعلية."""

import asyncio
import json

import memory_hook as mh


def _run(coro):
    return asyncio.run(coro)


def _install_fake_httpx(monkeypatch, get_payload=None, get_status=200, raise_exc=None):
    """يستبدل httpx.AsyncClient بعميل وهمي يسجّل النداءات (POST/GET)."""
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
            return _Resp(200, {"stored": True})

        async def get(self, url, params=None, headers=None):
            if raise_exc:
                raise raise_exc
            recorder["calls"].append(("GET", url, params, headers))
            return _Resp(get_status, get_payload if get_payload is not None else {"memories": []})

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
    rec = _install_fake_httpx(monkeypatch, get_payload={"memories": [{"content": "fact1"}]})
    data = {
        "litellm_call_id": "rid-1",
        "proxy_server_request": {"headers": {"x-openwebui-user-id": "u1"}},
        "messages": [{"role": "user", "content": "تذكّر: لوني أزرق"}],
    }
    out = _run(mh.MemoryHook().async_pre_call_hook(None, None, data, "completion"))
    methods = [c[0] for c in rec["calls"]]
    assert "POST" in methods and "GET" in methods
    post = next(c for c in rec["calls"] if c[0] == "POST")
    assert post[2] == {"user_id": "u1", "content": "لوني أزرق"}  # الحقيقة بعد البادئة
    assert post[3] == {"X-Request-ID": "rid-1"}  # request_id مُمرَّر
    assert out["messages"][0]["role"] == "system"
    assert "fact1" in out["messages"][0]["content"]  # الذاكرة حُقنت


def test_hook_read_only_no_write(monkeypatch):
    rec = _install_fake_httpx(monkeypatch, get_payload={"memories": [{"content": "fav"}]})
    data = {
        "litellm_call_id": "rid-2",
        "proxy_server_request": {"headers": {"x-openwebui-user-id": "u1"}},
        "messages": [{"role": "user", "content": "ما لوني؟"}],
    }
    out = _run(mh.MemoryHook().async_pre_call_hook(None, None, data, "completion"))
    methods = [c[0] for c in rec["calls"]]
    assert "POST" not in methods and "GET" in methods
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
