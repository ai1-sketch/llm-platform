"""اختبارات تكامل على **Postgres حقيقي** (ADR-019 §9/§13) — البوّابة التي تعدها المواصفة:
عزل per-user فعلي (شرط `WHERE user_id` يُنفَّذ على المحرّك، لا mock)، تطبيق `SCHEMA_DDL`،
مسار assemble ضمن الميزانية، وحذف-للنسيان. تُتخطّى إن غاب `MEMORY_TEST_DATABASE_URL`
(بيئة الوحدات بلا DB)؛ تُشغَّل في CI عبر خدمة postgres (pgvector).

المسار اللفظي مقصود (نُجبر فشل التضمين fail-soft) كي يختبر استعلام العزل الحقيقي بلا خدمة embeddings.
"""

import asyncio
import os
import uuid

import asyncpg  # حقيقي عند توفّره (conftest لا يُكفّئه حينها)؛ الاستيراد آمن (لا اتصال وقت التحميل)
import pytest
import retrieve as R
from arabic import normalize_ar
from rank import rank_items
from schema import SCHEMA_DDL

from compose import compose_context

pytestmark = pytest.mark.skipif(
    not os.environ.get("MEMORY_TEST_DATABASE_URL"),
    reason="MEMORY_TEST_DATABASE_URL غير مضبوط (لا Postgres حقيقي)",
)

DSN = os.environ.get("MEMORY_TEST_DATABASE_URL")


def _run(coro):
    return asyncio.run(coro)


async def _pool():
    pool = await asyncpg.create_pool(DSN, min_size=1, max_size=3)
    async with pool.acquire() as c:
        await c.execute(SCHEMA_DDL)  # idempotent bootstrap على DB حقيقي
    return pool


async def _insert(pool, user_id, content):
    async with pool.acquire() as c:
        await c.execute(
            "INSERT INTO memory.user_memory "
            "(user_id, content, content_hash, content_tsv, origin, writer) "
            "VALUES ($1,$2,$3, to_tsvector('simple',$4), 'user_explicit','hook')",
            user_id,
            content,
            uuid.uuid4().hex,
            normalize_ar(content),
        )


async def _cleanup(pool, *user_ids):
    async with pool.acquire() as c:
        for u in user_ids:
            await c.execute("DELETE FROM memory.user_memory WHERE user_id=$1", u)


def _no_embeddings(monkeypatch):
    async def _boom(_t):
        raise RuntimeError("no embeddings service in integration test")

    monkeypatch.setattr(R, "embed_one", _boom)  # fail-soft → مسار لفظي فقط


def test_schema_ddl_creates_three_stores():
    async def _t():
        pool = await _pool()
        try:
            async with pool.acquire() as c:
                rows = await c.fetch(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='memory'"
                )
            names = {r["table_name"] for r in rows}
            assert {"user_memory", "conversation_memory", "file_memory"} <= names
        finally:
            await pool.close()

    _run(_t())


def test_per_user_isolation_real_db(monkeypatch):
    _no_embeddings(monkeypatch)
    u1, u2 = f"itest-{uuid.uuid4()}", f"itest-{uuid.uuid4()}"

    async def _t():
        pool = await _pool()
        try:
            await _insert(pool, u1, "لون المستخدم المفضل هو الازرق")
            await _insert(pool, u2, "لون المستخدم المفضل هو الاحمر السري")
            res1 = await R.retrieve(pool, u1, "المفضل", tables=("user_memory",))
            t1 = [m.text for m, _ in res1]
            assert t1, "u1 يجب أن يسترجع حقيقته"
            assert all("الاحمر" not in t for t in t1), "تسرّب! u1 رأى سرّ u2"
            assert any("الازرق" in t for t in t1)
            res2 = await R.retrieve(pool, u2, "المفضل", tables=("user_memory",))
            t2 = [m.text for m, _ in res2]
            assert all("الازرق" not in t for t in t2), "تسرّب! u2 رأى ذاكرة u1"
            assert any("الاحمر" in t for t in t2), "u2 يجب أن يرى حقيقته (تماثل الاتجاهين)"
        finally:
            await _cleanup(pool, u1, u2)
            await pool.close()

    _run(_t())


def test_assemble_path_within_budget_real_db(monkeypatch):
    _no_embeddings(monkeypatch)
    u = f"itest-{uuid.uuid4()}"

    async def _t():
        pool = await _pool()
        try:
            for i in range(8):
                await _insert(pool, u, f"حقيقة {i}: المستخدم يحب البرمجة واللون الازرق")
            cand = await R.retrieve(pool, u, "يحب", tables=("user_memory",))
            result = compose_context(rank_items(cand), budget_tokens=400)
            assert result.block, "يجب أن تُنتَج كتلة سياق غير فارغة"
            assert result.tokens <= 400  # byte-count ≥ real ⇒ التوكنات الحقيقية ≤ 400 أيضاً
        finally:
            await _cleanup(pool, u)
            await pool.close()

    _run(_t())


def test_delete_for_forgetting_real_db(monkeypatch):
    _no_embeddings(monkeypatch)
    u1, u2 = f"itest-{uuid.uuid4()}", f"itest-{uuid.uuid4()}"

    async def _t():
        pool = await _pool()
        try:
            await _insert(pool, u1, "سر المستخدم الاول")
            await _insert(pool, u2, "سر المستخدم الثاني")
            async with pool.acquire() as c:
                await c.execute("DELETE FROM memory.user_memory WHERE user_id=$1", u1)
            assert await R.retrieve(pool, u1, "المستخدم", tables=("user_memory",)) == []
            r2 = await R.retrieve(pool, u2, "المستخدم", tables=("user_memory",))
            assert any("الثاني" in m.text for m, _ in r2), "u2 يجب أن يبقى سليماً"
        finally:
            await _cleanup(pool, u1, u2)
            await pool.close()

    _run(_t())
