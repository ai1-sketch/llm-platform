# llm-platform — منصّة LLM الداخلية للشركة

منصّة خدمة نماذج لغوية (LLM) داخلية، تبدأ صغيرة على جهاز واحد ومصمّمة للنمو إلى السحابة دون إعادة بناء. المبدأ المركزي: **توحيد كل شيء خلف OpenAI-compatible API + حاويات Docker + إعدادات خارجية** — *"نفس الشكل، صناديق أكبر"*.

> **الحالة:** ما قبل الكود — الحوكمة مثبّتة، لا يوجد منطق تطبيق بعد. التالي: Phase 1 (P-01..P-05).
>
> 🧭 **للبدء أو الاستئناف بعد أي انقطاع: اقرأ [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md) أولاً.**

## 🗺️ خريطة الحوكمة

| الوثيقة | الدور |
|--------|------|
| [CLAUDE.md](CLAUDE.md) | عقد المساعد — يُحمّل تلقائياً، القواعد غير القابلة للتفاوض |
| [docs/CONSTITUTION.md](docs/CONSTITUTION.md) | الدستور الأعلى: الفلسفة، القوانين، معيار "تمّ"، آلية العمل |
| [docs/ARCHITECTURE_RULES.md](docs/ARCHITECTURE_RULES.md) | المجلدات، الطبقات، الاستيراد، التسمية، config-driven |
| [docs/ERROR_AND_OBSERVABILITY_POLICY.md](docs/ERROR_AND_OBSERVABILITY_POLICY.md) | عقيدة "الخطأ يبلّغ عن نفسه" + الرصد |
| [docs/DECISIONS.md](docs/DECISIONS.md) | سجل القرارات المعمارية (ADR) |
| [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md) | خريطة التتبّع الحيّة — نقطة الاستئناف |
| [PROJECT_BLUEPRINT.md](PROJECT_BLUEPRINT.md) | المخطّط الهندسي الكامل (الخلفية + التفاصيل) |

## ⚖️ المبادئ الحاكمة (مختصر)
- العقد الثابت: كل تخاطب عبر **OpenAI-compatible API**.
- الطبقات: **Open WebUI → LiteLLM → محرّك → موديل** (لا تجاوز، اتجاه واحد).
- **نظيف ≠ معقّد.** ابدأ بسيط (YAGNI)؛ أي توسّع بقرار ADR.
- **الجودة أولاً، لا اختصارات.** والخطأ يبلّغ عن نفسه.

## ▶️ التالي
Phase 1: `docker-compose` يشغّل **Open WebUI + LiteLLM + Postgres** أمام موديل **managed**. التفاصيل والأهداف في [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md) (P-01..P-05).
