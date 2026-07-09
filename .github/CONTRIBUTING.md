# المساهمة في llm-platform

> اقرأ أولاً: [docs/PROGRESS_MAP.md](../docs/PROGRESS_MAP.md) (نقطة الاستئناف) ثم [docs/CONSTITUTION.md](../docs/CONSTITUTION.md) (الحاكم الأعلى).

## القواعد غير القابلة للتفاوض
- **الجودة أولاً، لا اختصارات** (R-LAW-01)؛ معيار "تمّ" في CONSTITUTION §3.
- **anti-bloat / YAGNI** (R-LAW-02): لا قاعدة/أداة/طبقة قبل عبور حارس §5 — القرار الافتراضي "لا".
- **كل قرار معماري = ADR** في [docs/DECISIONS.md](../docs/DECISIONS.md) (R-ADR-01/02/03).
- **كل مرور موديل عبر البوّابة** (R-LAW-05/R-ARCH-10، ADR-023) — لا اتصال مباشر بمحرّك. *(الاستثناء الوحيد الموثّق: تضمين OWUI المحلي خارج البوّابة، ADR-025.)*
- **الخطأ يبلّغ عن نفسه**: JSON + `request_id` عبر الطبقات، لا ابتلاع صامت (ERROR_AND_OBSERVABILITY_POLICY).

## بوّابة الجودة (محلياً قبل كل commit)
المسار الأساسي بلا كود بايثون (محرّك السياق متقاعد إلى فرع `future/context-engine`، ADR-025):
```bash
ruff check . && ruff format --check .        # lint/format (يمرّ بلا ملفات بايثون)
docker compose -f compose/docker-compose.yml --env-file /tmp/ci.env config -q   # صحّة compose
pre-commit install                           # يفرض نفس فحوص CI على كل commit
```
نفس الفحوص تُفرَض في CI ([.github/workflows/ci.yml](workflows/ci.yml)). *(mypy + pytest من سلسلة [ADR-008](../docs/DECISIONS.md) يعودان متى عاد كود بايثون للمسار الأساسي.)* كل تغيير ذي قيمة يمرّ ببوّابة مراجعة §4. مسار القراءة الكامل في [README](../README.md).

## رسائل الـ commit
وصفية، تربط ADR/البند، وتُنهى بـ `Co-Authored-By` عند المساهمة بمساعدة AI.
