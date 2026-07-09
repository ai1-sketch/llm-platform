# PROGRESS_MAP — خريطة التتبّع الحيّة (Resume Point)

> **R-PROG-00 (أعلى أولوية):** هذا **أوّل ملف يُقرأ عند الاستئناف**. حدّثه **بعد كل خطوة ذات قيمة** (التحديث جزء من الخطوة لا اختياري). سجّل **القرارات المعمارية فقط** في [DECISIONS](DECISIONS.md) كـ ADR — لا يلزم لمسه في كل تغيير. عند ضياع السياق، هذا الملف هو مصدر الحقيقة.
>
> الحالة: `[ ]` لم يبدأ · `[~]` جارٍ · `[x]` تمّ. كل بند `P-NN` منجَز يربط PR/قرار في [DECISIONS](DECISIONS.md). مرجع DoD في [CONSTITUTION](CONSTITUTION.md) §3.

> **آخر تحديث:** 2026-07-09 · **المحدِّث:** Chief Architect (طبقة رصد الأداء Prometheus+Grafana — [ADR-031](DECISIONS.md)؛ + تصحيح ادّعاء observability؛ فوق إصلاحات Codex)

---

## 1. الحالة الآن (سطر واحد)
**P-01 شغّال end-to-end ✅ — المحرّك = vLLM ([ADR-028](DECISIONS.md))، والمسار الأساسي يعتمد OWUI كلياً (RAG + Memory المدمجة، [ADR-025](DECISIONS.md)).** **5 خدمات** (Open WebUI → LiteLLM → vllm/GPU + **نسختا postgres مخصّصتان**: `postgres-litellm` لحالة البوّابة و`postgres-openwebui`/pgvector لبيانات OWUI — [ADR-030](DECISIONS.md)، الشكل المحلي يطابق الإنتاج). **تخزين OWUI على PostgreSQL + pgvector** (بدل SQLite/Chroma — [ADR-029](DECISIONS.md)، قرار أساسي دائم + least-privilege؛ الموقع قابل للانتقال لخارجي/مُدار بتغيير رابط). موديل الاختبار = **Qwen3 4B** (`Qwen/Qwen3-4B-AWQ` — الموديل تفصيل config قابل للتبديل بسطرين في `config/vllm/vllm-config.yaml`؛ "Sankari Chat" = اسم الواجهة، ADR-017). **الرؤية معلّقة مؤقتاً** (لا multimodal يتّسع على 6GB تحت vLLM — تعود مع GPU أكبر، ADR-028). الذاكرة/الملفات عبر OWUI المدمج (`ENABLE_MEMORIES=true`؛ RAG مستندات). الواجهة على http://127.0.0.1:3000 (تشغيل/أعطال: [RUNBOOK](RUNBOOK.md)). محرّك السياق المخصّص متقاعد إلى فرع `future/context-engine` (ADR-025). التالي: **تجهيز تبديل الموديل لـ Gemini** عند النشر (config-only عبر البوّابة) / تخطيط Phase 2.

## 2. أُنجِز مؤخّراً
> **ملاحظة تاريخية:** البنود أدناه سجلّ زمني. الحالة **الحالية** = **5 خدمات** (open-webui · litellm · vllm · postgres-litellm · postgres-openwebui — [ADR-030](DECISIONS.md)). أي ذكر قديم لخدمتَي `memory`/`embeddings` (عصر "الخمس خدمات" **القديم** قبل ADR-025) أو لـ"4 خدمات" كحاضرٍ يصف حالة **سابقة**؛ وكذلك أي ذكر لـ`llamacpp`/llama-swap/`Gemma 4`/GGUF (المحرّك الحالي = **vllm** وموديل الاختبار = **Qwen3 4B** — [ADR-028](DECISIONS.md))، ولـ SQLite/Chroma كتخزين (الحالي = PostgreSQL+pgvector — [ADR-029](DECISIONS.md)). هذا القسم (مع [DECISIONS](DECISIONS.md) وتاريخ git) هو **سجلّ التغييرات المعتمد** — لا حاجة لـ CHANGELOG منفصل.

- [x] **📊 طبقة رصد الأداء (النوع الثاني) + تصحيح رصد الأخطاء (2026-07-09، [ADR-031](DECISIONS.md)، قرار المالك — فرع `feat/observability`، بانتظار الدمج):** بُني النوع الثاني: **Prometheus + Grafana** خلف `profiles: [monitoring]` (لا يقلعان افتراضياً؛ قابلان للحذف بعلَم) يكشط vLLM `/metrics` (KV%/طابور/TTFT/tokens-s/preemptions/prefix-cache) + لوحة "vLLM Inference" ككود. **مُتحقَّق حيّاً:** prometheus يكشط vLLM + litellm الحيّين (targets up)، استعلام Grafana→Prometheus ناجح، litellm `/metrics` مُفعّل عبر callback (بمفتاح token)، prefix caching مُفعّل (94% إصابة تحت حمل)، ونسب الإنفاق per-user مُثبَتة (dept-ali/ahmad مفصولان). والنوع الأول صُحّح: تضييق ادّعاء R-ERR-15/16/19 (الانتشار عبر الطبقات مؤجَّل — تقاعد memory/ADR-025) + ضبط خصوصية stdout على INFO (حُذف `turn_off_message_logging` كـ no-op مخالف §5) + دوران سجلّات + إنفاق per-user + BLE001. الحارس/CI/‏.env.example محدَّثة (7 خدمات). كل بوّابات CI + التحقّق الحيّ خضراء.
- [x] **🔒 معالجة مراجعة Codex المستقلّة (2026-07-09، دُمجت على master، commit `6c83321`):** 3 إصلاحات مؤكَّدة أغفلها التدقيق السابق — (1) **دوران كلمات سرّ postgres** عبر `ALTER ROLE ... PASSWORD` idempotent في سكربتَي init (**مُثبَت حيّاً** بحاوية pgvector عابرة: إعادة التطبيق بكلمة جديدة تُدوّر الاعتماد والبصمة تتغيّر، الكلمة القديمة تُرفَض، لا تكرار دور/قاعدة)؛ (2) **تقوية `check_invariants.py`** — إمساك خدمة مطلوبة ناقصة + فرض تثبيت الصور بـ `@sha256` + رفض تتبّع `.env`/`backups`/`models` في git (**6 اختبارات سلبية** خضراء)؛ (3) **حلّ تناقض "كل المرور عبر البوّابة"** في `SECURITY.md`/`CONTRIBUTING.md` بإقرار استثناء تضمين OWUI المحلي ([ADR-025](DECISIONS.md)). + "نافذة أوّل-أدمن" وسلاسل التوريد لقائمة "قبل التعريض"، وبانر `PROJECT_BLUEPRINT` يعدّد البقايا القديمة. **كل البوّابات خضراء:** ruff + `check_invariants` + `docker compose config -q` + دوران postgres حيّ. (إصلاحات تنفّذ ADR-026/029/030/025 القائمة — لا ADR جديد.)
- [x] **🏗️ نسخة postgres مخصّصة لكل تطبيق (2026-07-02، [ADR-030](DECISIONS.md)، قرار المالك):** رُفض الاعتماد على نسخة مشتركة — `postgres-litellm` (حالة البوّابة) + `postgres-openwebui` (بيانات OWUI/pgvector)، كلتاهما بنموذج least-privilege الكامل (أدمن معزول + دور تطبيق + REVOKE) عبر init لكل نسخة. المبرّر: **الشكل المحلي يطابق شكل الإنتاج** — لا "تعديل فكرة + توثيق + إعادة عمل" عند النشر الفعلي. **مُتحقَّق حيّاً:** عزل بنيوي (دور كل تطبيق غير موجود على نسخة الآخر — اختبار سلبي)، litellm ‏74 جدولاً وOWUI ‏43 + vector 0.8.3 كلٌّ على نسخته، 5 خدمات healthy، دخان 200. R-ARCH-31/R-ERR-16 والفحص الآلي محدَّثة (5 خدمات).
- [x] **🗄️ تخزين OWUI → PostgreSQL + pgvector + أدوار least-privilege (2026-07-02، [ADR-029](DECISIONS.md)، قرار أساسي دائم؛ طوبولوجيا النسخة المشتركة استُبدلت بـ ADR-030):** نُقل OWUI من SQLite+Chroma إلى قاعدة `openwebui` داخل **نفس خدمة postgres** (صفر خدمة جديدة، R-ARCH-31 أخضر)؛ pgvector صار مُستخدَماً فعلاً (يُفعّل ADR-020). **فصل أدوار بقرار المالك** ("لا نبني على أساس غلط"): superuser ‏`postgres` للإدارة فقط، والتطبيقات بأدوار عادية تملك قاعدتها فقط + `REVOKE CONNECT FROM PUBLIC` — أُعيدت تهيئة الـ volume من الصفر عبر `init/10-app-roles.sh` (يبني كل شيء تلقائياً على volume نظيف — DoD §3). **مُتحقَّق حيّاً:** الأدوار الثلاثة بصلاحياتها الصحيحة + اختبار سلبي بالاتجاهين (CONNECT مرفوض) + litellm ‏74 جدولاً وOWUI ‏43 جدولاً (منها `access_grant`) + `document_chunk.vector` + مفتاح OWUI أُعيد توليده + دخان 200. مراجعة عدائية (6 مؤكَّدة) عولجت — منها حارس CRLF (‏`.gitattributes`). **قابلية التبديل موثّقة:** المحرّك (PG+pgvector) ثابت دائم؛ موقعه (محلي ↔ خارجي/مُدار) وطوبولوجيته = تغيير رابط/‏pg_dump فقط.
- [x] **🚀 التحوّل إلى محرّك vLLM (2026-07-02، [ADR-028](DECISIONS.md)):** بعد دراسة موثّقة (3 وكلاء بحث + 4 تحقّقات عدائية): **Gemma 4 تحت vLLM على 6GB مدحوض** (أصغر checkpoint قابل للخدمة 8.3GB — PLE/embeddings تبقى bf16؛ GGUF مرفوضة؛ علّة أداء Ada مفتوحة vllm#38887) → قرار المالك: **vLLM محرّكاً وحيداً + موديل اختبار `Qwen/Qwen3-4B-AWQ`** (غير مقفل، ~2.5GB، تنزيل تلقائي من HF). الخدمة `llamacpp`→`vllm` (R-ARCH-31/R-ERR-16 + فحص الثوابت محدَّثة)، إعداد المحرّك في `config/vllm/vllm-config.yaml`، بادئة `hosted_vllm/`، إزالة `max_tokens` الافتراضي (vLLM يرفض 400 بدل القصّ)، الرؤية معلّقة حتى GPU أكبر. تجربة llama-swap (ADR-027) انتهت — محفوظة في git history.
- [x] **تجربة موديل محلّي أكبر (2026-06-29، [ADR-027](DECISIONS.md) — انتهت، مُستبدَلة بـ ADR-028):** llama-swap → **موديلان قابلان للاختيار على 6GB** (`Gemma 4` E2B + `Gemma 4 4B` E4B، تبديل في الـ VRAM عند الطلب). **مُتحقَّق حيّاً:** E4B يتّسع (4.76GB/6) وأجاب مباشرةً ("القاهرة")، بينما E2B استنزف التوكنات تفكيراً بلا جواب — دليل عملي على قيمة موديل أكبر قبل قرار Gemini.
- [x] **جودة التوثيق + حوكمة قابلة للتنفيذ (2026-06-29):** تدقيق توثيق (6 أبعاد) + تقييم "عين جديدة" (4 مراجعين مستقلّين، **7/10**) → مزامنة الوثائق مع ADR-025، قابلية تدقيق ADR (حقل §5 + فهرس حالة)، إصلاح PROJECT_BLUEPRINT (**12 مرسى ميتاً → 0**) + [RUNBOOK](RUNBOOK.md)، و**فحص ثوابت معمارية آليّ في CI** + تقوية `ENABLE_SIGNUP` + نسخ احتياطي ([ADR-026](DECISIONS.md)). (PRs #3–#6.)
- [x] **التحوّل إلى OWUI-أساسي ([ADR-025](DECISIONS.md), 2026-06-26):** أُزيل محرّك السياق المخصّص من master (4 خدمات)، ومحفوظ على فرع `future/context-engine`. **مُتحقَّق حيّاً على الصورة المثبّتة:** ذاكرة OWUI (تخزين + استرجاع دلالي مسافة 0.83 + **حقن في ردّ Gemma**: "الفيروزي") · RAG مستندات (رفع + استخراج + تضمين Chroma + **استرجاع + استشهادات [1] في ردّ Gemma**: "ياقوت-أزرق-2026"). التضمين = all-MiniLM-384 محلّي خارج البوّابة. حساب الاختبار نُظّف بالكامل.
- [x] إثبات جدوى محلي (Qwen3 / Gemma عبر llama.cpp).
- [x] كتابة [PROJECT_BLUEPRINT](../PROJECT_BLUEPRINT.md) (المعمارية + فلسفة "نفس الشكل، صناديق أكبر").
- [x] سجلّ القرارات [DECISIONS](DECISIONS.md) (ADR-001…ADR-007).
- [x] [CONSTITUTION](CONSTITUTION.md) + [ARCHITECTURE_RULES](ARCHITECTURE_RULES.md) + [ERROR_AND_OBSERVABILITY_POLICY](ERROR_AND_OBSERVABILITY_POLICY.md).
- [x] هذا الملف (نقطة الاستئناف + أهداف `P-NN`).
- [x] **توحيد المواقع:** نُقل `DECISIONS.md` و `ERROR_AND_OBSERVABILITY_POLICY.md` إلى `llm-platform/docs/` بجوار البقية؛ كل الروابط النسبية تُحلّ.
- [x] إنشاء `CLAUDE.md` (تابع للدستور) بالاسم الموحّد `ERROR_AND_OBSERVABILITY_POLICY.md`.
- [x] حسم تعارض اسم خدمة LiteLLM: وُحّد على `litellm` عبر كل الوثائق (انظر القسم 6).
- [x] إنشاء `README.md` (مدخل بشري + خريطة الحوكمة)، وتثبيت `PROJECT_BLUEPRINT.md` في جذر المشروع (R-ARCH-03).
- [x] تسجيل قرار **أدوات الجودة** كـ [ADR-008](DECISIONS.md) (مقترح) + بند **P-00** (بوّابة قبل أوّل كود).
- [x] **P-00 محسوم:** لجنة تقييم (4 خبراء) + مراجعة عدائية → [ADR-008](DECISIONS.md) "مقبول". وحسم META-BLOAT كـ [ADR-009](DECISIONS.md).
- [x] **scaffolding + بداية P-01:** كُتبت ملفات الأساس (`pyproject.toml`, `.pre-commit-config.yaml`, `compose/docker-compose.yml`, `config/litellm/litellm-config.yaml`, `config/env/.env.example`, `.gitignore`) ومُرّت على لجنة مراجعة (4 عدسات + تحقّق ويب)؛ طُبِّقت 3 must (healthcheck بايثون بدل curl، إزالة بادئة `sk-`، إزالة فرض التغطية) + shoulds رخيصة.
- [x] **محرّك Gemma 4 في الـ stack:** بعد تحقّق DevOps (gemma4 مدعوم بصورة `server-cuda` الرسمية)، أُضيفت خدمة `llamacpp` (GPU + الموديل عبر `MODEL_DIR`) وLiteLLM يشير للمحرّك المحلي ([ADR-011](DECISIONS.md)).
- [x] **🎉 P-01 شغّال end-to-end (2026-06-24):** Docker Desktop + GPU passthrough (RTX 4050 داخل الحاوية) + 4 خدمات healthy (حينها؛ صارت 5 بعد إضافة `memory`) + Gemma 4 محمّل على GPU (~2.4GB) + طلب نجح عبر البوّابة (الموديل Gemma 4 → "2 + 2 equals 4"، مع reasoning). الواجهة على http://127.0.0.1:3000.
- [x] **قرار الذاكرة + تحقّق الهوية:** مسح موسوعي ([MEMORY_LANDSCAPE](../research/MEMORY_LANDSCAPE.md)) → [ADR-012](DECISIONS.md) (Mem0 خلف hook + per-user + HITL + pgvector + Qwen3-Embedding). **أُثبت end-to-end** أن `ENABLE_FORWARD_USER_INFO_HEADERS` يمرّر `X-OpenWebUI-User-Id` للـ LiteLLM hook (مستخدم حقيقي UUID) — أساس العزل per-user. شرط أمني: البوّابة داخلية.
- [x] **🧠 ذاكرة المرحلة 1 (L1) شغّالة end-to-end:** خدمة `memory` (FastAPI+asyncpg، جدول `memory.user_memory` معزول per-user، مُختبَرة: u2 لا يرى ذاكرة u1) + LiteLLM hook (`memory_hook.py`: يقرأ الهوية، يحقن الذاكرة في system، يخزّن عند "remember:"/"تذكّر:" = HITL، fail-open). اختبار حقيقي عبر OWUI: خزّن "favorite color teal" → استرجعه في محادثة منفصلة ✅. (L1 = صريح؛ بلا embedding/vector بعد.)
- [x] **سدّ ثغرات التوثيق:** [ADR-013](DECISIONS.md) (تنفيذ L1 مخصّص بدل Mem0 لـ Phase 1)، [ADR-014](DECISIONS.md) + [VISION_SETUP](../research/VISION_SETUP.md) (قرار وبحث الرؤية)، وتحديث R-ARCH-31 (إضافة خدمة `memory`). الرينيم (company-chat→Sankari Chat، WEBUI_NAME) مطبّق. **checkpoint v3 محفوظ** (commit `7898e1f`، tag `v3-memory-l1`).
- [x] **🔍 تدقيق اتساق + إصلاح ثغرات (2026-06-25، workflow متعدّد الوكلاء — 7 وكلاء):** كشف وأُصلح بدليل ملموس وتحقّق حيّ: **(1) حرج** — جدول `memory.user_memory` لم يكن يُنشئه أيّ كود (يفشل صامتاً على volume نظيف، رغم وسم "شغّال") → bootstrap idempotent في lifespan ([ADR-015](DECISIONS.md))، مُتحقَّق بإسقاط الـ schema وإعادة الإقلاع. **(2) P-05 مغلق** — `request_id` (litellm_call_id) يُمرَّر litellm→memory + سطر كلفة per-request + تسجيل JSON مهيكل في كودنا (`memory_hook.py` + `memory/app.py`)؛ **نفس المعرّف عبر الطبقات** (R-ERR-15/16/19، مُتحقَّق بـ grep حيّ). **(3)** اسم الموديل علامة حياديّة ([ADR-016](DECISIONS.md)) + تصحيح تعليقات متناقضة. **(4)** تحديث README (كان "ما قبل الكود/managed/3 خدمات")، وتعليقات compose/ARCHITECTURE_RULES (5 خدمات + `services/`)، وملاحظة CTX للرؤية.
- [x] **👁️ تفعيل الرؤية (2026-06-25، [ADR-014](DECISIONS.md)):** وُصل `mmproj-F16.gguf` لـ llamacpp (`--mmproj` + `--no-mmproj-offload` المُسقِط على CPU + `--image-max-tokens 256`) + `supports_vision: true` في litellm + ctx=4096 (آمن على 6GB). الأعلام مُتحقَّقة ضد الـ binary الفعلي. **مُتحقَّق حيّاً:** الموديل أجاب "أزرق" على صورة مربّع أزرق عبر OWUI→LiteLLM→llama-server؛ VRAM ~3.1–3.3GB/6GB (مريح)، بلا OOM ولا `n_embd mismatch`.
- [x] **🧪 شبكة أمان (تقوية P-01، 2026-06-25، تجسيد [ADR-008](DECISIONS.md)):** مجموعة **pytest (17 اختبار)** في `tests/` لخدمة الذاكرة والـ hook (conftest يُكفّئ litellm/asyncpg، بلا DB فعلي) تغطّي: bootstrap المخطط، عزل per-user، كشف "تذكّر:"، حقن الذاكرة، fail-open، تمرير request_id، سطر الكلفة، middleware. + **تثبيت إصدارات pre-commit** (ruff v0.12.0, mypy v2.1.0, gitleaks v8.30.1, hooks v6.0.0) + **CI** (`.github/workflows/ci.yml`: ruff+format+mypy+pytest+gitleaks على كل push/PR). البوّابة خضراء محلياً (ruff ✅ mypy ✅ 17 pytest ✅). أُضيف `_require_pool()` في `app.py` (أمان + فحص أنواع).
- [x] **🧹 توحيد المشروع (2026-06-25، [ADR-018](DECISIONS.md)):** رُقِّي محتوى `llm-platform/` إلى **جذر المستودع** (المستودع = المنصّة، عبر `git mv` محافظاً على الوسوم v1–v7). النموذج الأولي القديم → `legacy/` (متتبَّع، مستثنى من ruff عبر `extend-exclude`). حُذفت البيئات/النماذج القابلة لإعادة الإنشاء (`.venv*`, `wheels/`, `models/` القديم ≈ عشرات آلاف الملفات + ~7.4GB). صُحِّحت المسارات (compose `../models-gemma4`، CI بلا `working-directory`) ودُمج `.gitignore`. **مُتحقَّق:** 5 خدمات healthy من الجذر + POST `/v1/chat/completions`=200 (Gemma 4) + البوّابة خضراء؛ البيانات محفوظة (named volumes). ثم رُفع لمستودع GitHub خاص (`ai1-sketch/llm-platform`) مع CI أخضر.
- [x] **🔐 إتمام تقوية P-01 (2026-06-25):** **(1) virtual key** — وُلِّد مفتاح LiteLLM افتراضي (alias `open-webui`) عبر `/key/generate` وحلّ محلّ المفتاح الرئيسي في `.env` (الواجهة لم تعد تستخدم master → قابل للإبطال والعزو). **(2) تثبيت digests** — الصور الخمس (llamacpp, litellm, open-webui, postgres + python base للذاكرة) مُثبَّتة بـ `@sha256` (إعادة إنتاج حتمية). **مُتحقَّق حيّاً:** POST=200 عبر المفتاح الافتراضي، 5 خدمات healthy، الصور بـ digest في `compose config`.
- [x] **🧠 تصميم Context Engine (ذاكرة L2، 2026-06-25):** دراسة موسوعية (5 وكلاء) + ورشة تصميم (16 خبيراً + مراجعة عدائية) → قرار حلّ مخصّص. كُتبت المواصفة المفهرسة [specs/CONTEXT_ENGINE_V1.md](specs/CONTEXT_ENGINE_V1.md) + [ADR-019](DECISIONS.md) + [ADR-020](DECISIONS.md) (pgvector، يعدّل P-01). **↦ هذا المسار مُتقاعد لاحقاً إلى فرع `future/context-engine` ([ADR-025](DECISIONS.md))؛ استُبدل كأساس بـ OWUI المدمج.**
- [x] **🔬 تدقيق شامل + معالجة (2026-06-26، workflow 74 وكيلاً → 55 اكتشافاً مؤكَّداً):** عولجت كل المراتب بـ**بروتوكول التحقّق العدائي** (لكل دفعة: تنفيذ → تحقّق حيّ → 2–3 مراجعين مستقلّين → checkpoint). نتائج بارزة: **H1** ميزانية واعية بالنافذة + عدّ توكنات = بايتات (مراجعة عدائية كشفت تجاوز نافذة حقيقياً) [ADR-021]؛ **H2** اختبارات تكامل Postgres حقيقي (عزل per-user مُنفَّذ فعلاً، CI gate)؛ **M1** كل تضمين عبر البوّابة [ADR-022/023، قرار المالك]؛ **M2** تعليمة Qwen3 + request_id؛ **M3** فشل صاخب؛ **M5/M6** unaccent + uuid [ADR-024] + README؛ **LOW** non-root + .dockerignore + reqs مثبّتة + CI build + متانة + حوكمة + ملفّات معيارية. 9 دفعات، tags `rem-*`.

## 3. التالي مباشرةً (Next Up)
> أمسك بنداً واحداً، نفّذه، ثم حدّث القسمين 2 و 3 (والقسم 1).

1. [x] **تقوية P-01 — مكتملة:** ✓ virtual key (بدل master) · ✓ digests الصور الخمس · ✓ max_tokens=2048 *(أُزيل لاحقاً في [ADR-028](DECISIONS.md) — vLLM يرفض بدل أن يقصّ)* · ✓ رصد P-05 · ✓ رؤية *(معلّقة لاحقاً — ADR-028)* · ✓ اختبارات+CI · ✓ توحيد الجذر + GitHub خاص. كلها مُتحقَّقة حيّاً وقتها.
2. [↦ فرع] **Context Engine (ذاكرة L2) — متقاعد إلى `future/context-engine` ([ADR-025](DECISIONS.md)).** بُني M0→M4b ومُتحقَّق حيّاً (استرجاع دلالي هجين RRF + حقن في الدردشة + التقاط محادثة)، ثم **استُبدل كمسار أساسي بذاكرة/RAG المدمجة في OWUI**. **لا عمل عليه على master**؛ يُستأنف من الفرع عند مبرّر (موديل أقوى/حجم). المرجع التصميمي: [specs/CONTEXT_ENGINE_V1.md](specs/CONTEXT_ENGINE_V1.md).
3. [x] **التحوّل إلى vLLM — مُنفَّذ ([ADR-028](DECISIONS.md), 2026-07-02):** المحرّك صار نسخة الهدف السحابي نفسها؛ ترقية GPU/موديل = قيم config فقط.
4. [ ] **تجهيز تبديل الموديل لـ Gemini** عند النشر (config-only في `litellm-config.yaml` عبر البوّابة — R-ARCH-45 / [ADR-023](DECISIONS.md)).
5. [ ] **استعادة الرؤية (الصور)** عند GPU أكبر: تبديل الموديل في `vllm-config.yaml` لموديل multimodal (بلا mmproj — ADR-028).
6. [ ] التخطيط لـ Phase 2 للمنصّة (سحابة — نفس محرّك vLLM على GPU أكبر).

---

## 4. أهداف Phase 1 — البوّابة + الواجهة (1–10 مستخدمين)

| المعرّف | الهدف | الحالة |
|---|---|---|
| **P-00** | حسم أدوات الجودة وعتباتها وتوثيق المبرّر — [ADR-008](DECISIONS.md). (القرار محسوم؛ إنشاء ملفات الـ scaffolding هو بند "التالي مباشرةً".) | [x] |
| **P-01** | `compose/docker-compose.yml` يشغّل `open-webui` + `litellm` + المحرّك المحلي (`vllm` منذ [ADR-028](DECISIONS.md)) + قاعدتَي postgres المخصّصتين ([ADR-030](DECISIONS.md)) بـ `docker compose up`. | [x] **شغّال end-to-end** (5 خدمات healthy، GPU داخل الحاوية، طلب عبر البوّابة نجح، الواجهة على :3000؛ أُعيد التحقّق حيّاً بعد ADR-028/029/030) |
| **P-02** | `litellm-config.yaml`: موديل محلي واحد خلف العقد `/v1` (بدأ Gemma 4 — [ADR-010](DECISIONS.md)؛ حالياً Qwen3 4B — [ADR-028](DECISIONS.md))؛ managed = تبديل سطر واحد. | [x] |
| **P-03** | `config/env/.env.example` يغطّي كل المفاتيح المطلوبة (لا قيم حقيقية). | [x] |
| **P-04** | منفذ البوّابة غير مكشوف؛ الوصول داخل شبكة Docker فقط (R-ARCH-24). | [x] |
| **P-05** | رصد بحدّ أدنى: كل مسار طلب يُصدر `request_id` + سجلّ كلفة (سياسة الرصد). | [x] **عند البوّابة** (litellm: `litellm_call_id` + سطر الكلفة، JSON)؛ الانتشار عبر الطبقات تراجع بتقاعد `memory` (ADR-025) → مؤجَّل |

## 5. Phase 2+ — صناديق أكبر (محجوز، ليس الآن)

| المعرّف | الهدف | الحالة |
|---|---|---|
| **P-10** | التوسّع السحابي: نفس محرّك `vLLM` (المعتمد محلياً منذ [ADR-028](DECISIONS.md)) على GPU سحابي أكبر — يفرضه طلب حجم/خصوصية حقيقي. | [ ] |

> لا يُضاف بند Phase 2+ قبل عبور حارس التضخيم ([CONSTITUTION](CONSTITUTION.md) §5) وتسجيل المبرّر في [DECISIONS](DECISIONS.md).

---

## 6. أسئلة / عوائق مفتوحة
> صيغة كل بند: `[OPEN] الوصف — مالكه — أثره`.

- [RESOLVED] **تعارض اسم خدمة LiteLLM:** وُحّد حقل `service` على `litellm` في `ERROR_AND_OBSERVABILITY_POLICY` ليطابق `R-ARCH-31` واسم خدمة Docker (يدعم تتبّع `request_id` عبر الطبقات R-ERR-19).
- [RESOLVED] الـ backend الابتدائي = **موديل Gemma 4 المحلي** (قرار المالك، [ADR-010](DECISIONS.md))؛ managed تبديل سطر واحد لاحقاً.
- [RESOLVED] تشغيل المحرّك = **Docker مع GPU** (قرار المالك، [ADR-011](DECISIONS.md)).
- [RESOLVED] صورة `ghcr.io/ggml-org/llama.cpp:server-cuda` **تدعم gemma4** (master يومي، الدعم منذ إبريل 2026) — لا حاجة لصورة مخصّصة. شرط: تعريف NVIDIA لويندوز يدعم WSL2 GPU + Docker Desktop WSL2.
- [RESOLVED] **تحقّق أوّل تشغيل:** GPU داخل الحاوية مؤكَّد (RTX 4050) + Gemma 4 محمّل بلا "unknown architecture" + healthchecks تعمل (5 خدمات healthy).
- [OPEN] **R-ERR-15/16/19 (انتشار request_id عبر الطبقات):** على master الحالي مؤكَّد **عند البوّابة فقط** (litellm: `litellm_call_id` + سطر الكلفة، JSON). الانتشار الكامل عبر OWUI/vLLM أُثبت تاريخياً بخدمة `memory` (`memory_hook.py` + `memory/app.py`) المتقاعدة إلى `future/context-engine` ([ADR-025](DECISIONS.md)) — مؤجَّل حتى أوّل adapter نملكه. (صُحّح الادّعاء 2026-07-09: مراجعة Codex + تدقيق observability.)
- [OPEN] أين تُخزَّن الأسرار؟ `.env` محلي الآن مقابل secret manager لاحقاً — Tech Lead — يؤثّر على بنية Compose.
- [OPEN] مُحفِّز self-host الحقيقي (خصوصية/حجم)؟ — Owner — يؤجَّل حتى طلب فعلي (YAGNI).

## 7. أثر القرارات (روابط لـ DECISIONS)
> الكامل في **[DECISIONS](DECISIONS.md)** بصيغة ADR. ملخّص:

| القرار | ملخّص | المرجع |
|---|---|---|
| العقد الثابت | توحيد كل شيء خلف **OpenAI-compatible API** | ADR-001 |
| البوّابة | **LiteLLM** بوّابة مركزية إلزامية | ADR-002 |
| الواجهة | **Open WebUI** متّصلة حصراً بـ LiteLLM | ADR-003 |
| محرّك الاستدلال | llama.cpp أولاً → **vLLM** (تحقّق فعلاً — ADR-028) بنفس العقد | ADR-004 |
| التشغيل | **Docker Compose أولاً** | ADR-005 |
| نقطة البدء | موديل managed أولاً (**مُستبدَل بـ ADR-010**) | ADR-006 |
| نطاق المرحلة الأولى | **لا** Kubernetes / SSO / HA / autoscaling (YAGNI) | ADR-007 |
| المحرّك المحلي | مبدأ الموديل المحلي أولاً (بدأ Gemma 4؛ الموديل الحالي Qwen3 4B — ADR-028) | ADR-010/011 |
| اسم الموديل/العلامة | الموديل باسمه الصادق (حالياً "Qwen3 4B")، الواجهة = "Sankari Chat" | ADR-016/017 |
| الرؤية | تفعيل الصور (mmproj) عبر العقد — **معلّقة بعد ADR-028** حتى GPU أكبر | ADR-014 |
| التضمين عبر البوّابة | كل تضمين عبر LiteLLM (model-agnostic) | ADR-023 |
| **الحاكم: OWUI أساسي** | اعتماد OWUI RAG+Memory؛ **تقاعد المحرّك المخصّص** إلى فرع | **ADR-025** |
| حوكمة قابلة للتنفيذ + تقوية | فحص ثوابت معمارية في CI + `ENABLE_SIGNUP=false` + نسخ احتياطي | ADR-026 |
| تجربة: موديلان محلّيان | llama-swap (Gemma 4 E2B + 4B) — **مُستبدَل بـ ADR-028** | ADR-027 |
| **المحرّك الحالي: vLLM** | vLLM محرّكاً وحيداً + موديل اختبار Qwen3-4B-AWQ؛ الرؤية معلّقة حتى GPU أكبر | **ADR-028** |
| **التخزين الأساسي: PG+pgvector** | تخزين OWUI على PostgreSQL+pgvector (بدل SQLite/Chroma) + least-privilege؛ قابل للانتقال لخارجي/مُدار | **ADR-029** |
| **الطوبولوجيا: نسخة لكل تطبيق** | postgres-litellm + postgres-openwebui (الشكل المحلي = شكل الإنتاج، 5 خدمات) | **ADR-030** |
| **رصد الأداء: Prometheus+Grafana** | مقاييس vLLM خلف profile monitoring (تجاوز §5 واعٍ للجاهزية) + تصحيح ادّعاء observability | **ADR-031** |

---

### كيفية التحديث (تذكير)
- بعد كل خطوة ذات قيمة: انقل البند من القسم 3 → 2، حدّث القسم 1 وتاريخ آخر تحديث.
- قرار **معماري** فقط؟ سجّله كـ ADR في [DECISIONS](DECISIONS.md) ثم أضف صفّاً في القسم 7 (التغييرات غير المعمارية لا تلمس DECISIONS).
- عائق جديد؟ أضفه في القسم 6 بصيغة `[OPEN]`؛ احذفه عند الحلّ.
