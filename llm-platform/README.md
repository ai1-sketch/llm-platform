# llm-platform — منصّة LLM الداخلية للشركة

منصّة خدمة نماذج لغوية (LLM) داخلية، تبدأ صغيرة على جهاز واحد ومصمّمة للنمو إلى السحابة دون إعادة بناء. المبدأ المركزي: **توحيد كل شيء خلف OpenAI-compatible API + حاويات Docker + إعدادات خارجية** — *"نفس الشكل، صناديق أكبر"*.

> **الحالة:** Phase 1 (P-01) **شغّال end-to-end** ✅ — 5 خدمات محاواة + ذاكرة per-user (L1). الواجهة على http://127.0.0.1:3000.
>
> 🧭 **للبدء أو الاستئناف بعد أي انقطاع: اقرأ [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md) أولاً.**

## 🏗️ المعمارية الحالية (5 خدمات)

```text
open-webui ──/v1──▶ litellm ──/v1──▶ llamacpp (Gemma 4، GPU) ──▶ GGUF
 (الواجهة)          (البوّابة)         (المحرّك)
                       ├──▶ postgres (حالة البوّابة)
                       └──▶ memory   (ذاكرة per-user L1، عبر hook داخل litellm)
```

كل تخاطب عبر العقد `OpenAI /v1`؛ تبديل المحرّك/المزوّد = تعديل سطر واحد في `config/litellm/litellm-config.yaml`. اسم الموديل المعروض = **Gemma 4**؛ و**Sankari Chat** = اسم الواجهة/التطبيق (`WEBUI_NAME`) لا اسم الموديل ([ADR-017](docs/DECISIONS.md)). البوّابة والمحرّك والذاكرة **غير مكشوفة** (R-ARCH-24)؛ المنفذ العام الوحيد = الواجهة.

## 🗺️ خريطة الحوكمة

| الوثيقة | الدور |
|--------|------|
| [CLAUDE.md](CLAUDE.md) | عقد المساعد — يُحمّل تلقائياً، القواعد غير القابلة للتفاوض |
| [docs/CONSTITUTION.md](docs/CONSTITUTION.md) | الدستور الأعلى: الفلسفة، القوانين، معيار "تمّ"، آلية العمل |
| [docs/ARCHITECTURE_RULES.md](docs/ARCHITECTURE_RULES.md) | المجلدات، الطبقات، الاستيراد، التسمية، config-driven |
| [docs/ERROR_AND_OBSERVABILITY_POLICY.md](docs/ERROR_AND_OBSERVABILITY_POLICY.md) | عقيدة "الخطأ يبلّغ عن نفسه" + الرصد |
| [docs/DECISIONS.md](docs/DECISIONS.md) | سجل القرارات المعمارية (ADR-001..016) |
| [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md) | خريطة التتبّع الحيّة — نقطة الاستئناف |
| [PROJECT_BLUEPRINT.md](PROJECT_BLUEPRINT.md) | المخطّط الهندسي الكامل (الخلفية + التفاصيل) |

## ⚖️ المبادئ الحاكمة (مختصر)
- العقد الثابت: كل تخاطب عبر **OpenAI-compatible API**.
- الطبقات: **Open WebUI → LiteLLM → محرّك → موديل** (لا تجاوز، اتجاه واحد)، وخدمة **memory** جانبية خلف الـ hook.
- **نظيف ≠ معقّد.** ابدأ بسيط (YAGNI)؛ أي توسّع بقرار ADR.
- **الجودة أولاً، لا اختصارات.** والخطأ يبلّغ عن نفسه (JSON + `request_id` عبر الطبقات).

## ▶️ التشغيل
من جذر `llm-platform` (شرط مسبق: Docker Desktop بخلفية WSL2 + تعريف NVIDIA يدعم GPU):

```bash
cp config/env/.env.example config/env/.env    # ثم املأ القيم وولّد الأسرار
docker compose --env-file config/env/.env -f compose/docker-compose.yml up -d
```

**التالي:** تقوية P-01 (virtual key بدل master-key، تثبيت وسوم الصور) · ذاكرة Phase 2 (استرجاع دلالي) · تفعيل الرؤية ([ADR-014](docs/DECISIONS.md)). كل التفاصيل وحالة البنود في [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md).
