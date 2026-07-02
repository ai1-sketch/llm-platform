# llm-platform — منصّة LLM الداخلية للشركة

منصّة خدمة نماذج لغوية (LLM) داخلية، تبدأ صغيرة على جهاز واحد ومصمّمة للنمو إلى السحابة دون إعادة بناء. المبدأ المركزي: **توحيد كل شيء خلف OpenAI-compatible API + حاويات Docker + إعدادات خارجية** — *"نفس الشكل، صناديق أكبر"*.

> **الحالة:** Phase 1 شغّال end-to-end ✅ — **5 خدمات** محاواة + CI. المحرّك = **vLLM** (موديل اختبار Qwen3 4B، [ADR-028](docs/DECISIONS.md)؛ الرؤية معلّقة مؤقتاً حتى GPU أكبر). الذاكرة/الملفات عبر ميزات **Open WebUI المدمجة** (RAG + Personalization Memory، [ADR-025](docs/DECISIONS.md))، تخزينها على **PostgreSQL + pgvector بنسخة مخصّصة** ([ADR-029](docs/DECISIONS.md)/[ADR-030](docs/DECISIONS.md)). الواجهة على http://127.0.0.1:3000.
>
> 🧭 **للبدء أو الاستئناف بعد أي انقطاع: اقرأ [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md) أولاً.**
>
> 🧪 **محرّك السياق المخصّص** (ذاكرة دلالية L2: M0–M4b) **متقاعد إلى فرع [`future/context-engine`](https://github.com/ai1-sketch/llm-platform/tree/future/context-engine)** كميزة تطوير مستقبلية ([ADR-025](docs/DECISIONS.md)) — ليس على المسار الأساسي.

## 🏗️ المعمارية (5 خدمات)

```text
open-webui ──/v1──▶ litellm ──/v1──▶ vllm (Qwen3 4B، GPU) ──▶ HF model
 (الواجهة +   │      (البوّابة)
  RAG+Memory) │         └──▶ postgres-litellm (حالة البوّابة: مفاتيح/كلفة)
              └──▶ postgres-openwebui + pgvector (بيانات OWUI: ميتاداتا + متجهات — ADR-029/030)
```

كل تخاطب موديل عبر العقد `OpenAI /v1` والبوّابة. تبديل المحرّك/المزوّد = سطر واحد في `config/litellm/litellm-config.yaml`؛ تبديل موديل vLLM = سطران في `config/vllm/vllm-config.yaml` (التنزيل تلقائي من HuggingFace — [ADR-028](docs/DECISIONS.md)). اسم الموديل المعروض = **Qwen3 4B** (تسمية صادقة)؛ و**Sankari Chat** = اسم الواجهة (`WEBUI_NAME`) لا الموديل ([ADR-017](docs/DECISIONS.md)). البوّابة والمحرّك وقاعدتا postgres **غير مكشوفة** (R-ARCH-24)؛ المنفذ العام الوحيد = الواجهة.

## 🧠 الذاكرة والملفات (Open WebUI المدمج)
بعد [ADR-025](docs/DECISIONS.md)، تتولّى Open WebUI طبقة البيانات: **RAG للمستندات** (تقطيع + استرجاع top-k + استشهادات + استخراج متعدّد الصيغ) و**ذاكرة per-user** (`Settings > Personalization > Memory`، `ENABLE_MEMORIES=true`). التخزين على **PostgreSQL + pgvector بنسخة مخصّصة** (`postgres-openwebui`، بدل SQLite/Chroma — [ADR-029](docs/DECISIONS.md)/[ADR-030](docs/DECISIONS.md)، أساس دائم؛ الموقع قابل للانتقال لخارجي/مُدار بتغيير رابط). محرّك السياق المخصّص (تضمين عبر البوّابة + استرجاع hybrid + التقاط محادثة تلقائي عابر للجلسات) محفوظ على فرع `future/context-engine` لتطوير مستقبلي.

## 🗺️ خريطة الحوكمة

> **مسار القراءة:** [PROGRESS_MAP](docs/PROGRESS_MAP.md) (الحالة) ← [CONSTITUTION](docs/CONSTITUTION.md) (القوانين) ← [ARCHITECTURE_RULES](docs/ARCHITECTURE_RULES.md) / [ERROR_AND_OBSERVABILITY_POLICY](docs/ERROR_AND_OBSERVABILITY_POLICY.md) (التفاصيل) ← [DECISIONS](docs/DECISIONS.md) (لماذا).

| الوثيقة | الدور |
|--------|------|
| [CLAUDE.md](CLAUDE.md) | عقد المساعد — يُحمّل تلقائياً، القواعد غير القابلة للتفاوض |
| [docs/CONSTITUTION.md](docs/CONSTITUTION.md) | الدستور الأعلى: الفلسفة، القوانين، معيار "تمّ"، آلية العمل |
| [docs/ARCHITECTURE_RULES.md](docs/ARCHITECTURE_RULES.md) | المجلدات، الطبقات، الاستيراد، التسمية، config-driven |
| [docs/ERROR_AND_OBSERVABILITY_POLICY.md](docs/ERROR_AND_OBSERVABILITY_POLICY.md) | عقيدة "الخطأ يبلّغ عن نفسه" + الرصد |
| [docs/DECISIONS.md](docs/DECISIONS.md) | سجل القرارات المعمارية (ADR-001..030) |
| [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md) | خريطة التتبّع الحيّة — نقطة الاستئناف |
| [PROJECT_BLUEPRINT.md](PROJECT_BLUEPRINT.md) | المخطّط الهندسي الكامل (الرؤية + الخلفية) |
| **مرجع / متقاعد** | [docs/specs/CONTEXT_ENGINE_V1.md](docs/specs/CONTEXT_ENGINE_V1.md) + [research/](research/) (CONTEXT_ENGINE_RATIONALE · MEMORY_LANDSCAPE · VISION_SETUP) — مواصفة محرّك السياق المتقاعد + الأبحاث الداعمة ([ADR-025](docs/DECISIONS.md)) |

## ⚖️ المبادئ الحاكمة (مختصر)
- العقد الثابت: كل تخاطب موديل عبر **OpenAI-compatible API** والبوّابة.
- الطبقات: **Open WebUI → LiteLLM → محرّك → موديل** (لا تجاوز، اتجاه واحد).
- **نظيف ≠ معقّد.** ابدأ بسيط (YAGNI)؛ أي توسّع بقرار ADR.
- **الجودة أولاً، لا اختصارات.** والخطأ يبلّغ عن نفسه (JSON + `request_id` عبر الطبقات).

## ▶️ التشغيل
شرط مسبق: Docker Desktop (خلفية WSL2) + تعريف NVIDIA يدعم GPU **بإصدار R580+** (صورة المحرّك CUDA 13 — [ADR-028](docs/DECISIONS.md)). من **جذر المستودع**:

1. **الأسرار:** `cp config/env/.env.example config/env/.env`، ثم املأ القيم وولّد الأسرار (`openssl rand -hex 32`) — اترك `OPENWEBUI_LITELLM_KEY` على قيمته المؤقتة الآن (يُولَّد في الخطوة 3 بعد إقلاع البوّابة). *(لا تنزيل موديل يدوي — vLLM يسحب الموديل المحدّد في `config/vllm/vllm-config.yaml` تلقائياً من HuggingFace أوّل تشغيل؛ `HF_TOKEN` فقط للموديلات المقفلة — [ADR-028](docs/DECISIONS.md).)*
2. **التشغيل:**
   ```bash
   docker compose --env-file config/env/.env -f compose/docker-compose.yml up -d
   ```
3. **الـ virtual key (مرة واحدة):** بعد أن تصبح `litellm` بحالة healthy، ولّد `OPENWEBUI_LITELLM_KEY` بالأمر الجاهز في [docs/RUNBOOK.md](docs/RUNBOOK.md)، ضعه في `.env`، ثم `docker compose … up -d open-webui` لإعادة تحميل الواجهة به.
4. **تحقّق:** افتح http://127.0.0.1:3000 وأرسل رسالة (أوّل إقلاع لـ vLLM يأخذ دقائق: تنزيل + torch.compile). إن ظهر خطأ، راجع حالة الخدمات وسجلّاتها (`docker compose … ps` / `logs`). فحص GPU المسبق: `docker run --rm --gpus all nvidia/cuda:13.0.2-base-ubuntu22.04 nvidia-smi`. **تفاصيل التشغيل والأعطال الشائعة: [docs/RUNBOOK.md](docs/RUNBOOK.md).**

## 🧪 التطوير (Developer setup)
المسار الأساسي بلا كود بايثون؛ بوّابة الجودة = **ruff (lint/format) + gitleaks** + تحقّق `compose config` (تُفرَض في CI: [.github/workflows/ci.yml](.github/workflows/ci.yml)). *(mypy + pytest من سلسلة [ADR-008](docs/DECISIONS.md) يعودان تلقائياً متى عاد كود بايثون للمسار الأساسي.)*

```bash
pip install ruff==0.12.0 pre-commit
ruff check . && ruff format --check .
pre-commit install                       # مرآة فحوص CI لكل commit
```

البنية: المشروع في جذر المستودع؛ `legacy/` = النموذج الأولي المؤرشَف (Qwen3/Gemma، غير مُشغَّل، خارج البوّابة). **كل التفاصيل وحالة البنود في [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md).**
