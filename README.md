# llm-platform — منصّة LLM الداخلية للشركة

منصّة خدمة نماذج لغوية (LLM) داخلية، تبدأ صغيرة على جهاز واحد ومصمّمة للنمو إلى السحابة دون إعادة بناء. المبدأ المركزي: **توحيد كل شيء خلف OpenAI-compatible API + حاويات Docker + إعدادات خارجية** — *"نفس الشكل، صناديق أكبر"*.

> **الحالة:** Phase 1 شغّال end-to-end ✅ — **4 خدمات** محاواة + رؤية (صور) + CI. الذاكرة/الملفات عبر ميزات **Open WebUI المدمجة** (RAG + Personalization Memory، [ADR-025](docs/DECISIONS.md)). الواجهة على http://127.0.0.1:3000.
>
> 🧭 **للبدء أو الاستئناف بعد أي انقطاع: اقرأ [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md) أولاً.**
>
> 🧪 **محرّك السياق المخصّص** (ذاكرة دلالية L2: M0–M4b) **متقاعد إلى فرع [`future/context-engine`](https://github.com/ai1-sketch/llm-platform/tree/future/context-engine)** كميزة تطوير مستقبلية ([ADR-025](docs/DECISIONS.md)) — ليس على المسار الأساسي.

## 🏗️ المعمارية (4 خدمات)

```text
open-webui ──/v1──▶ litellm ──/v1──▶ llamacpp (Gemma 4، GPU) ──▶ GGUF
 (الواجهة +        (البوّابة)         └──▶ postgres (pgvector: حالة litellm)
  RAG + Memory)
```

كل تخاطب موديل عبر العقد `OpenAI /v1` والبوّابة. تبديل المحرّك/المزوّد = سطر واحد في `config/litellm/litellm-config.yaml`. اسم الموديل المعروض = **Gemma 4**؛ و**Sankari Chat** = اسم الواجهة (`WEBUI_NAME`) لا الموديل ([ADR-017](docs/DECISIONS.md)). البوّابة والمحرّك وpostgres **غير مكشوفة** (R-ARCH-24)؛ المنفذ العام الوحيد = الواجهة.

## 🧠 الذاكرة والملفات (Open WebUI المدمج)
بعد [ADR-025](docs/DECISIONS.md)، تتولّى Open WebUI طبقة البيانات: **RAG للمستندات** (تقطيع + استرجاع top-k + استشهادات + استخراج متعدّد الصيغ) و**ذاكرة per-user** (`Settings > Personalization > Memory`، `ENABLE_MEMORIES=true`). محرّك السياق المخصّص (تضمين عبر البوّابة + استرجاع hybrid + التقاط محادثة تلقائي عابر للجلسات) محفوظ على فرع `future/context-engine` لتطوير مستقبلي.

## 🗺️ خريطة الحوكمة

| الوثيقة | الدور |
|--------|------|
| [CLAUDE.md](CLAUDE.md) | عقد المساعد — يُحمّل تلقائياً، القواعد غير القابلة للتفاوض |
| [docs/CONSTITUTION.md](docs/CONSTITUTION.md) | الدستور الأعلى: الفلسفة، القوانين، معيار "تمّ"، آلية العمل |
| [docs/ARCHITECTURE_RULES.md](docs/ARCHITECTURE_RULES.md) | المجلدات، الطبقات، الاستيراد، التسمية، config-driven |
| [docs/ERROR_AND_OBSERVABILITY_POLICY.md](docs/ERROR_AND_OBSERVABILITY_POLICY.md) | عقيدة "الخطأ يبلّغ عن نفسه" + الرصد |
| [docs/DECISIONS.md](docs/DECISIONS.md) | سجل القرارات المعمارية (ADR-001..025) |
| [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md) | خريطة التتبّع الحيّة — نقطة الاستئناف |
| [PROJECT_BLUEPRINT.md](PROJECT_BLUEPRINT.md) | المخطّط الهندسي الكامل (الخلفية + التفاصيل) |

## ⚖️ المبادئ الحاكمة (مختصر)
- العقد الثابت: كل تخاطب موديل عبر **OpenAI-compatible API** والبوّابة.
- الطبقات: **Open WebUI → LiteLLM → محرّك → موديل** (لا تجاوز، اتجاه واحد).
- **نظيف ≠ معقّد.** ابدأ بسيط (YAGNI)؛ أي توسّع بقرار ADR.
- **الجودة أولاً، لا اختصارات.** والخطأ يبلّغ عن نفسه (JSON + `request_id` عبر الطبقات).

## ▶️ التشغيل
شرط مسبق: Docker Desktop (خلفية WSL2) + تعريف NVIDIA يدعم GPU. من **جذر المستودع**:

1. **حمّل ملفّ الموديل** (GGUF — كبير، خارج git) → `models-gemma4/`: `gemma-4-E2B-it-qat-*.gguf` + `mmproj-F16.gguf` (للرؤية).
2. **الأسرار:** `cp config/env/.env.example config/env/.env`، ثم املأ القيم وولّد الأسرار (`openssl rand -hex 32`)، وولّد الـ virtual key (`OPENWEBUI_LITELLM_KEY`) من litellm عبر `/key/generate`.
3. **التشغيل:**
   ```bash
   docker compose --env-file config/env/.env -f compose/docker-compose.yml up -d
   ```

## 🧪 التطوير (Developer setup)
المسار الأساسي بلا كود بايثون؛ بوّابة الجودة = **ruff (lint/format) + gitleaks** (تُفرَض في CI: [.github/workflows/ci.yml](.github/workflows/ci.yml)) + التحقّق من صحّة compose:

```bash
pip install ruff==0.12.0 pre-commit
ruff check . && ruff format --check .
pre-commit install                       # مرآة فحوص CI لكل commit
```

البنية: المشروع في جذر المستودع؛ `legacy/` = النموذج الأولي المؤرشَف (Qwen3/Gemma، غير مُشغَّل، خارج البوّابة). **كل التفاصيل وحالة البنود في [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md).**
