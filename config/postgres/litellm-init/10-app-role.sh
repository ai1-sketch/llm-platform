#!/bin/bash
# llm-platform — تهيئة نسخة postgres-litellm المخصّصة (ADR-030): least-privilege (ADR-029).
# superuser (postgres) للإدارة فقط؛ التطبيق يتصل بدور `litellm` العادي الذي يملك قاعدته فقط.
# يعمل تلقائياً على volume نظيف (docker-entrypoint-initdb.d)؛ إعادة تطبيقه يدوياً: RUNBOOK. idempotent.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -v app_pw="$LITELLM_DB_PASSWORD" <<'EOSQL'
SELECT 'CREATE ROLE litellm LOGIN PASSWORD ' || quote_literal(:'app_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'litellm')\gexec
-- دوران كلمة السرّ: CREATE أعلاه يتخطّى دوراً موجوداً، فلا يُحدّث كلمة السرّ عند تغيير .env.
-- ALTER (idempotent) يزامنها فعلاً عند إعادة تطبيق السكربت يدوياً على volume موجود (RUNBOOK).
ALTER ROLE litellm WITH LOGIN PASSWORD :'app_pw';
SELECT 'CREATE DATABASE litellm OWNER litellm'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'litellm')\gexec
-- لا CONNECT افتراضي عبر PUBLIC (يحمي من أي دور مستقبلي على هذه النسخة)
REVOKE CONNECT ON DATABASE litellm FROM PUBLIC;
GRANT CONNECT ON DATABASE litellm TO litellm;
EOSQL
