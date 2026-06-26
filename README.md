# llm-platform — منصّة LLM الداخلية للشركة

منصّة خدمة نماذج لغوية (LLM) داخلية، تبدأ صغيرة على جهاز واحد ومصمّمة للنمو إلى السحابة دون إعادة بناء. المبدأ المركزي: **توحيد كل شيء خلف OpenAI-compatible API + حاويات Docker + إعدادات خارجية** — *"نفس الشكل، صناديق أكبر"*.

> **الحالة:** Phase 1 شغّال end-to-end ✅ — **6 خدمات** محاواة + **Context Engine (ذاكرة دلالية L2)** + رؤية (صور) + اختبارات (وحدات + تكامل Postgres حقيقي) و CI. الواجهة على http://127.0.0.1:3000.
>
> 🧭 **للبدء أو الاستئناف بعد أي انقطاع: اقرأ [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md) أولاً.**

## 🏗️ المعمارية (6 خدمات)

```text
open-webui ──/v1──▶ litellm ──/v1──▶ llamacpp (Gemma 4، GPU) ──▶ GGUF
 (الواجهة)          (البوّابة)      ├──▶ embeddings (Qwen3-Embedding، CPU)  ◀─ memory يطلب التضمين عبر البوّابة
                       │            └──▶ postgres (pgvector: حالة litellm + جداول memory)
                       └──(hook)──▶ memory (Context Engine per-user)
```

كل تخاطب عبر العقد `OpenAI /v1`، و**كل مرور موديل عبر البوّابة بلا استثناء** ([ADR-023](docs/DECISIONS.md)). تبديل المحرّك/المزوّد = سطر واحد في `config/litellm/litellm-config.yaml`. اسم الموديل المعروض = **Gemma 4**؛ و**Sankari Chat** = اسم الواجهة (`WEBUI_NAME`) لا الموديل ([ADR-017](docs/DECISIONS.md)). البوّابة والمحرّكان والذاكرة وpostgres **غير مكشوفة** (R-ARCH-24)؛ المنفذ العام الوحيد = الواجهة.

## 🧠 Context Engine (الذاكرة)
ذاكرة per-user **دلالية** خلف الـ hook: تخزين (`pgvector halfvec(1024)`) + استرجاع **هجين** (dense + lexical + RRF) + ترتيب حتمي + حقن **واعٍ بنافذة الموديل**. عزل صارم بـ `user_id` (مُختبَر على Postgres حقيقي). التفاصيل والقرارات في [docs/specs/CONTEXT_ENGINE_V1.md](docs/specs/CONTEXT_ENGINE_V1.md).

## 🗺️ خريطة الحوكمة

| الوثيقة | الدور |
|--------|------|
| [CLAUDE.md](CLAUDE.md) | عقد المساعد — يُحمّل تلقائياً، القواعد غير القابلة للتفاوض |
| [docs/CONSTITUTION.md](docs/CONSTITUTION.md) | الدستور الأعلى: الفلسفة، القوانين، معيار "تمّ"، آلية العمل |
| [docs/ARCHITECTURE_RULES.md](docs/ARCHITECTURE_RULES.md) | المجلدات، الطبقات، الاستيراد، التسمية، config-driven |
| [docs/ERROR_AND_OBSERVABILITY_POLICY.md](docs/ERROR_AND_OBSERVABILITY_POLICY.md) | عقيدة "الخطأ يبلّغ عن نفسه" + الرصد |
| [docs/DECISIONS.md](docs/DECISIONS.md) | سجل القرارات المعمارية (ADR-001..024) |
| [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md) | خريطة التتبّع الحيّة — نقطة الاستئناف |
| [PROJECT_BLUEPRINT.md](PROJECT_BLUEPRINT.md) | المخطّط الهندسي الكامل (الخلفية + التفاصيل) |

## ⚖️ المبادئ الحاكمة (مختصر)
- العقد الثابت: كل تخاطب عبر **OpenAI-compatible API**؛ كل مرور موديل عبر البوّابة.
- الطبقات: **Open WebUI → LiteLLM → محرّك → موديل** (لا تجاوز، اتجاه واحد)، وخدمتا `memory`/`embeddings` خلف البوّابة.
- **نظيف ≠ معقّد.** ابدأ بسيط (YAGNI)؛ أي توسّع بقرار ADR.
- **الجودة أولاً، لا اختصارات.** والخطأ يبلّغ عن نفسه (JSON + `request_id` عبر الطبقات).

## ▶️ التشغيل
شرط مسبق: Docker Desktop (خلفية WSL2) + تعريف NVIDIA يدعم GPU. من **جذر المستودع**:

1. **حمّل ملفّات الموديل** (GGUF — كبيرة، خارج git):
   - الدردشة → `models-gemma4/`: `gemma-4-E2B-it-qat-*.gguf` + `mmproj-F16.gguf` (للرؤية).
   - التضمين → `models-embeddings/`: `Qwen3-Embedding-0.6B-Q8_0.gguf`.
2. **الأسرار:** `cp config/env/.env.example config/env/.env`، ثم املأ القيم وولّد الأسرار (`openssl rand -hex 32`)، وولّد الـ virtual keys (`OPENWEBUI_LITELLM_KEY`، `MEMORY_LITELLM_KEY`) من litellm عبر `/key/generate`.
3. **التشغيل:**
   ```bash
   docker compose --env-file config/env/.env -f compose/docker-compose.yml up -d
   ```

## 🧪 التطوير (Developer setup)
بوّابة الجودة = **ruff + mypy + pytest + gitleaks** (تُفرَض في CI: [.github/workflows/ci.yml](.github/workflows/ci.yml)):

```bash
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install ruff==0.12.0 mypy==2.1.0 pytest pre-commit fastapi httpx asyncpg pydantic
.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m pytest -q   # وحدات
pre-commit install                                                          # مرآة فحوص CI لكل commit
```

اختبارات **التكامل** (عزل per-user على Postgres حقيقي) تعمل تلقائياً في CI، أو محلياً بضبط `MEMORY_TEST_DATABASE_URL`.

البنية: المشروع في جذر المستودع؛ `legacy/` = النموذج الأولي المؤرشَف (Qwen3/Gemma، غير مُشغَّل، خارج البوّابة). **كل التفاصيل وحالة البنود في [docs/PROGRESS_MAP.md](docs/PROGRESS_MAP.md).**
