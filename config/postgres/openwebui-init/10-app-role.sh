#!/bin/bash
# llm-platform — تهيئة نسخة postgres-openwebui المخصّصة (ADR-030): least-privilege (ADR-029).
# superuser (postgres) للإدارة فقط؛ التطبيق يتصل بدور `openwebui` العادي الذي يملك قاعدته فقط.
# يعمل تلقائياً على volume نظيف (docker-entrypoint-initdb.d)؛ إعادة تطبيقه يدوياً: RUNBOOK. idempotent.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -v app_pw="$OPENWEBUI_DB_PASSWORD" <<'EOSQL'
SELECT 'CREATE ROLE openwebui LOGIN PASSWORD ' || quote_literal(:'app_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'openwebui')\gexec
SELECT 'CREATE DATABASE openwebui OWNER openwebui'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'openwebui')\gexec
-- لا CONNECT افتراضي عبر PUBLIC (يحمي من أي دور مستقبلي على هذه النسخة)
REVOKE CONNECT ON DATABASE openwebui FROM PUBLIC;
GRANT CONNECT ON DATABASE openwebui TO openwebui;
EOSQL

# امتداد pgvector يحتاج صلاحية فائقة — يُنشأ هنا مرّة واحدة (ADR-029/030)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname openwebui -c "CREATE EXTENSION IF NOT EXISTS vector;"
