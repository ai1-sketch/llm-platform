"""اختبارات بناء DDL (نقي، بلا DB) — يضمن الامتدادات والجداول والفهارس وحتمية SCHEMA_DDL."""

from schema import EMBED_DIM, SCHEMA_DDL, build_schema_ddl


def test_required_extensions_present():
    # vector (متجهات) + pg_trgm + unaccent (بحث نصّي مُهيَّأ، ADR-020) — كلها idempotent
    for ext in ("vector", "pg_trgm", "unaccent"):
        assert f"CREATE EXTENSION IF NOT EXISTS {ext};" in SCHEMA_DDL


def test_three_stores_with_vector_and_indexes():
    for t in ("user_memory", "conversation_memory", "file_memory"):
        assert f"memory.{t}" in SCHEMA_DDL
        assert f"{t}_emb_hnsw" in SCHEMA_DDL  # فهرس HNSW على المتجه لكل مخزن
        assert f"{t}_tsv_gin" in SCHEMA_DDL  # فهرس GIN على tsvector
    assert f"halfvec({EMBED_DIM})" in SCHEMA_DDL and "halfvec(1024)" in SCHEMA_DDL


def test_idempotent_and_deterministic():
    assert SCHEMA_DDL.count("IF NOT EXISTS") >= 10  # bootstrap آمن على volume قائم
    assert build_schema_ddl() == SCHEMA_DDL  # حتمي (لا حالة/عشوائية)
