"""
مخطط Context Engine (M1، ADR-019) — DDL idempotent للمخازن الثلاثة بعقد أعمدة **موحّد**.
مصدر أعمدة المغلّف واحد (`ENVELOPE_COLUMNS`) يُولّد CREATE (للجدولين الجديدين) وALTER
(للجدول القائم user_memory) — يمنع انحراف المخطط بين المخازن (أخطر تحذير من المراجعة).
- user_memory: قائم (ADR-015) → نطوّره بـ ALTER ADD COLUMN IF NOT EXISTS (لا فقدان بيانات).
- conversation_memory / file_memory: جداول جديدة بنفس الأعمدة.
- المتجهات: halfvec(1024) + HNSW؛ النص: tsvector + GIN؛ كلاهما فهرس جزئي (status<>'deleted').
"""

EMBED_DIM = 1024  # مقيس فعلياً (M0.2)؛ تغييره = عمود v2 + backfill (مُصدَّر بالإصدار)

# الأعمدة الأساسية المشتركة (user_memory يملكها أصلاً من ADR-015)
_BASE = (
    "id bigserial PRIMARY KEY",
    "user_id text NOT NULL",
    "content text NOT NULL",
    "created_at timestamptz NOT NULL DEFAULT now()",
)

# مصدر الحقيقة الوحيد لأعمدة المغلّف (الاسم → التعريف). نفس القائمة لكل الجداول.
ENVELOPE_COLUMNS: list[tuple[str, str]] = [
    ("item_id", "uuid NOT NULL DEFAULT gen_random_uuid()"),
    ("source_type", "text NOT NULL DEFAULT 'user_fact'"),  # الافتراضي يُستبدَل لكل جدول جديد
    ("conversation_id", "text"),
    ("file_id", "text"),
    ("chunk_no", "int"),
    ("embedding", f"halfvec({EMBED_DIM})"),
    ("embedding_model_version", "text"),
    ("origin", "text NOT NULL DEFAULT 'user_explicit'"),
    ("writer", "text NOT NULL DEFAULT 'hook'"),
    ("source_ref", "text"),
    ("content_hash", "text"),
    ("confidence", "real NOT NULL DEFAULT 1.0"),
    ("importance", "real NOT NULL DEFAULT 0.5"),
    ("updated_at", "timestamptz NOT NULL DEFAULT now()"),
    ("last_accessed", "timestamptz"),
    ("token_estimate", "int"),
    ("status", "text NOT NULL DEFAULT 'active'"),
    ("metadata", "jsonb NOT NULL DEFAULT '{}'::jsonb"),
    ("content_tsv", "tsvector"),
]


def _envelope_for(src: str) -> list[tuple[str, str]]:
    return [
        (n, d.replace("DEFAULT 'user_fact'", f"DEFAULT '{src}'") if n == "source_type" else d)
        for n, d in ENVELOPE_COLUMNS
    ]


def _create_table(table: str, src: str) -> str:
    cols = list(_BASE) + [f"{n} {d}" for n, d in _envelope_for(src)]
    return f"CREATE TABLE IF NOT EXISTS memory.{table} (\n    " + ",\n    ".join(cols) + "\n);"


def _alter_user_memory() -> str:
    # نضمن وجود الجدول الأساسي (ADR-015) ثم نضيف أعمدة المغلّف بأمان
    base = "CREATE TABLE IF NOT EXISTS memory.user_memory (\n    " + ",\n    ".join(_BASE) + "\n);"
    alters = [
        f"ALTER TABLE memory.user_memory ADD COLUMN IF NOT EXISTS {n} {d};"
        for n, d in ENVELOPE_COLUMNS  # user_memory: source_type='user_fact' (الافتراضي الأصلي)
    ]
    return base + "\n" + "\n".join(alters)


def _indexes(table: str, scope_col: str | None, user_idx_name: str) -> str:
    idx = [
        f"CREATE UNIQUE INDEX IF NOT EXISTS {table}_item_id_uidx ON memory.{table}(item_id);",
        f"CREATE INDEX IF NOT EXISTS {user_idx_name} ON memory.{table}(user_id);",
        f"CREATE INDEX IF NOT EXISTS {table}_emb_hnsw ON memory.{table} "
        f"USING hnsw (embedding halfvec_cosine_ops) WHERE status <> 'deleted';",
        f"CREATE INDEX IF NOT EXISTS {table}_tsv_gin ON memory.{table} "
        f"USING gin (content_tsv) WHERE status <> 'deleted';",
    ]
    if scope_col:
        idx.append(
            f"CREATE INDEX IF NOT EXISTS {table}_{scope_col}_idx ON memory.{table}({scope_col});"
        )
    return "\n".join(idx)


def build_schema_ddl() -> str:
    parts = [
        "CREATE SCHEMA IF NOT EXISTS memory;",
        "CREATE EXTENSION IF NOT EXISTS vector;",
        "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
        "CREATE EXTENSION IF NOT EXISTS unaccent;",  # بحث نصّي مُهيَّأ (ADR-020)
        _alter_user_memory(),
        _create_table("conversation_memory", "conversation_chunk"),
        _create_table("file_memory", "document_chunk"),
        # user_memory يحتفظ باسم الفهرس القائم (ADR-015) لتجنّب التكرار
        _indexes("user_memory", None, "idx_user_memory_user"),
        _indexes("conversation_memory", "conversation_id", "conversation_memory_user_idx"),
        _indexes("file_memory", "file_id", "file_memory_user_idx"),
    ]
    return "\n\n".join(parts) + "\n"


SCHEMA_DDL = build_schema_ddl()
