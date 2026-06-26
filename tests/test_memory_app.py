"""اختبارات خدمة الذاكرة (FastAPI) — TestClient مع pool مُكفّأ، بلا قاعدة بيانات فعلية."""

import json
from unittest.mock import AsyncMock

import app as appmod
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[{"id": 1, "content": "c1"}])
    pool.fetchrow = AsyncMock(return_value={"id": 7})
    pool.execute = AsyncMock(return_value="DELETE 1")
    monkeypatch.setattr(appmod, "pool", pool)
    # بلا `with` → lifespan لا يعمل → يبقى الـ mock pool المحقون
    return TestClient(appmod.app), pool


def test_health(client):
    c, _ = client
    assert c.get("/health").json() == {"status": "ok"}


def test_list_scoped_by_user(client):
    c, pool = client
    r = c.get("/v1/memories", params={"user_id": "u1"})
    assert r.status_code == 200
    assert r.json()["memories"] == [{"id": 1, "content": "c1"}]
    assert "u1" in pool.fetch.call_args.args  # العزل: user_id يُمرَّر للاستعلام


def test_add_memory(client, monkeypatch):
    c, pool = client

    async def _fake_embed(_text, request_id=None):  # نتجنّب الشبكة + نختبر مسار "embedded"
        return [0.1] * 1024

    monkeypatch.setattr(appmod, "embed_one", _fake_embed)
    r = c.post("/v1/memories", json={"user_id": "u1", "content": "hello"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 7 and body["stored"] is True and body["embedded"] is True
    args = pool.fetchrow.call_args.args
    assert "u1" in args and "hello" in args  # العزل + المحتوى يُمرَّران للاستعلام


def test_add_memory_embed_fail_soft(client, monkeypatch):
    c, _ = client

    async def _boom(_text, request_id=None):
        raise RuntimeError("embeddings down")

    monkeypatch.setattr(appmod, "embed_one", _boom)
    r = c.post("/v1/memories", json={"user_id": "u1", "content": "hello"})
    assert r.status_code == 200  # الحقيقة تُخزَّن رغم عطل التضمين
    assert r.json()["embedded"] is False


def test_add_blank_content_400(client):
    c, _ = client
    r = c.post("/v1/memories", json={"user_id": "u1", "content": "   "})
    assert r.status_code == 400  # فراغ بعد التشذيب


def test_error_shape_unified_on_400(client):
    # خطأ العميل يعيد شكل OpenAI الموحّد (code + message + type + request_id) — R-ERR-06
    c, _ = client
    r = c.post(
        "/v1/memories", json={"user_id": "u1", "content": "   "}, headers={"X-Request-ID": "e1"}
    )
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "HTTP_ERROR" and err["type"] == "invalid_request_error"
    assert err["request_id"] == "e1"
    assert r.headers.get("x-request-id") == "e1"


def test_delete_one_scoped(client):
    c, pool = client
    r = c.delete("/v1/memories/5", params={"user_id": "u1"})
    assert r.status_code == 200
    args = pool.execute.call_args.args
    assert 5 in args and "u1" in args  # محصور بالـ id والمستخدم


def test_clear_all_scoped(client):
    c, pool = client
    r = c.delete("/v1/memories", params={"user_id": "u2"})
    assert r.status_code == 200
    assert "u2" in pool.execute.call_args.args


def test_capture_conversation_scoped(client, monkeypatch):
    c, pool = client

    async def _fe(_t, request_id=None):
        return [0.1] * 1024

    monkeypatch.setattr(appmod, "embed_one", _fe)
    r = c.post(
        "/v1/conversation/capture",
        json={
            "user_id": "u1",
            "conversation_id": "c1",
            "turns": [
                {"role": "user", "content": "أنا أحب القهوة"},
                {"role": "assistant", "content": "القهوة رائعة"},
            ],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["captured"] == 2 and body["received"] == 2
    args = pool.fetchrow.call_args.args  # آخر دور (assistant)
    assert "u1" in args and "c1" in args and "القهوة رائعة" in args  # العزل + scoping + المحتوى


def test_capture_dedup_not_counted(client, monkeypatch):
    c, pool = client
    pool.fetchrow = AsyncMock(return_value=None)  # ON CONFLICT DO NOTHING → لا إدراج

    async def _fe(_t, request_id=None):
        return [0.1] * 1024

    monkeypatch.setattr(appmod, "embed_one", _fe)
    r = c.post(
        "/v1/conversation/capture",
        json={
            "user_id": "u1",
            "conversation_id": "c1",
            "turns": [{"role": "user", "content": "x"}],
        },
    )
    assert r.json()["captured"] == 0  # مكرّر → غير محسوب


def test_capture_skips_blank_turn(client, monkeypatch):
    c, _ = client

    async def _fe(_t, request_id=None):
        return [0.1] * 1024

    monkeypatch.setattr(appmod, "embed_one", _fe)
    r = c.post(
        "/v1/conversation/capture",
        json={
            "user_id": "u1",
            "conversation_id": "c1",
            "turns": [{"role": "user", "content": "   "}],
        },
    )
    assert r.json()["captured"] == 0  # فارغ بعد التشذيب → لا إدراج


def test_middleware_request_id(client):
    c, _ = client
    r = c.get("/v1/memories", params={"user_id": "u1"})
    assert r.headers.get("x-request-id")  # يُولَّد إن غاب
    r2 = c.get("/v1/memories", params={"user_id": "u1"}, headers={"X-Request-ID": "abc"})
    assert r2.headers.get("x-request-id") == "abc"  # يُمرَّر كما هو


def test_log_shape(capsys):
    appmod._log("INFO", "C", "m", request_id="r")
    rec = json.loads(capsys.readouterr().out.strip())
    assert rec["service"] == "memory"
    assert rec["code"] == "C"
    assert rec["request_id"] == "r"
