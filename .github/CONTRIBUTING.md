# المساهمة في llm-platform

> اقرأ أولاً: [docs/PROGRESS_MAP.md](../docs/PROGRESS_MAP.md) (نقطة الاستئناف) ثم [docs/CONSTITUTION.md](../docs/CONSTITUTION.md) (الحاكم الأعلى).

## القواعد غير القابلة للتفاوض
- **الجودة أولاً، لا اختصارات** (R-LAW-01)؛ معيار "تمّ" في CONSTITUTION §3.
- **anti-bloat / YAGNI** (R-LAW-02): لا قاعدة/أداة/طبقة قبل عبور حارس §5 — القرار الافتراضي "لا".
- **كل قرار معماري = ADR** في [docs/DECISIONS.md](../docs/DECISIONS.md) (R-ADR-01/02/03).
- **كل مرور موديل عبر البوّابة** (R-LAW-05/R-ARCH-10، ADR-023) — لا اتصال مباشر بمحرّك.
- **الخطأ يبلّغ عن نفسه**: JSON + `request_id` عبر الطبقات، لا ابتلاع صامت (ERROR_AND_OBSERVABILITY_POLICY).

## بوّابة الجودة (محلياً قبل كل commit)
```bash
.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m ruff format --check .
MYPYPATH=services/memory .venv/Scripts/python -m mypy --config-file pyproject.toml services/memory/*.py config/litellm/memory_hook.py
.venv/Scripts/python -m pytest -q           # وحدات؛ التكامل عبر MEMORY_TEST_DATABASE_URL
pre-commit install                           # يفرض نفس فحوص CI على كل commit
```
نفس الفحوص تُفرَض في CI ([.github/workflows/ci.yml](workflows/ci.yml)). كل تغيير ذي قيمة يمرّ ببوّابة مراجعة §4.

## رسائل الـ commit
وصفية، تربط ADR/البند، وتُنهى بـ `Co-Authored-By` عند المساهمة بمساعدة AI.
