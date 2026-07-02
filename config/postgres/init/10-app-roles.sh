#!/bin/bash
# llm-platform — أدوار least-privilege (ADR-029): superuser (postgres) للإدارة فقط؛
# كل تطبيق يتصل بدور عادي يملك قاعدته فقط (litellm ← قاعدة litellm، openwebui ← قاعدة openwebui).
# لماذا: التطبيق المتصل بـ superuser = صلاحية مطلقة على كل القواعد عند أي اختراق،
# والـ superuser يتجاوز أي RLS مستقبلي (شرط مسبق لطبقة Data Asset — SECURITY.md "role split").
# يعمل تلقائياً على volume نظيف فقط (docker-entrypoint-initdb.d)؛ إعادة تطبيقه يدوياً: RUNBOOK.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
     -v litellm_pw="$LITELLM_DB_PASSWORD" -v owui_pw="$OPENWEBUI_DB_PASSWORD" <<'EOSQL'
-- أدوار التطبيقات (عاديّة، غير فائقة؛ idempotent)
SELECT 'CREATE ROLE litellm LOGIN PASSWORD ' || quote_literal(:'litellm_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'litellm')\gexec
SELECT 'CREATE ROLE openwebui LOGIN PASSWORD ' || quote_literal(:'owui_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'openwebui')\gexec
-- قاعدة لكل تطبيق يملكها دوره
SELECT 'CREATE DATABASE litellm OWNER litellm'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'litellm')\gexec
SELECT 'CREATE DATABASE openwebui OWNER openwebui'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'openwebui')\gexec
-- عزل صلب بين القاعدتين: لا CONNECT افتراضي عبر PUBLIC؛ كل دور يصل لقاعدته فقط
REVOKE CONNECT ON DATABASE litellm FROM PUBLIC;
REVOKE CONNECT ON DATABASE openwebui FROM PUBLIC;
GRANT CONNECT ON DATABASE litellm TO litellm;
GRANT CONNECT ON DATABASE openwebui TO openwebui;
EOSQL

# امتداد pgvector يحتاج صلاحية فائقة — يُنشأ هنا مرّة واحدة (ADR-029)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname openwebui -c "CREATE EXTENSION IF NOT EXISTS vector;"
