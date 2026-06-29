# PROGRESS_MAP — خريطة التتبّع الحيّة (Resume Point)

> **R-PROG-00 (أعلى أولوية):** هذا **أوّل ملف يُقرأ عند الاستئناف**. حدّثه **بعد كل خطوة ذات قيمة** (التحديث جزء من الخطوة لا اختياري). سجّل **القرارات المعمارية فقط** في [DECISIONS](DECISIONS.md) كـ ADR — لا يلزم لمسه في كل تغيير. عند ضياع السياق، هذا الملف هو مصدر الحقيقة.
>
> الحالة: `[ ]` لم يبدأ · `[~]` جارٍ · `[x]` تمّ. كل بند `P-NN` منجَز يربط PR/قرار في [DECISIONS](DECISIONS.md). مرجع DoD في [CONSTITUTION](CONSTITUTION.md) §3.

> **آخر تحديث:** 2026-06-26 · **المحدِّث:** Chief Architect (تحوّل معماري: OWUI أساسي، تقاعد محرّك السياق — ADR-025)

---

## 1. الحالة الآن (سطر واحد)
**P-01 شغّال end-to-end ✅ — المسار الأساسي يعتمد OWUI كلياً (RAG + Memory المدمجة، [ADR-025](DECISIONS.md)).** **4 خدمات** healthy (Open WebUI → LiteLLM → llamacpp/Gemma 4 GPU + postgres/pgvector). الموديل = **Gemma 4** ("Sankari Chat" = اسم الواجهة، ADR-017). الذاكرة/الملفات عبر ميزات OWUI المدمجة (`ENABLE_MEMORIES=true`؛ RAG مستندات). الرؤية تعمل (ADR-014). الواجهة على http://127.0.0.1:3000 (تشغيل/أعطال: [RUNBOOK](RUNBOOK.md)). **محرّك السياق المخصّص (M0–M4b: ذاكرة دلالية + التقاط محادثة + تضمين عبر البوّابة) متقاعد إلى فرع `future/context-engine`** (ADR-025) — ميزة تطوير مستقبلية، ليست على الأساسي. **التقاعد مُنجَز ومدموج في master** (PR #1 + تحقّق PR #2). التالي: **تجهيز تبديل الموديل لـ Gemini** عند النشر (config-only عبر البوّابة) / تخطيط Phase 2.

## 2. أُنجِز مؤخّراً
> **ملاحظة تاريخية:** البنود أدناه سجلّ زمني. أي ذكر لـ"5 خدمات" أو لخدمتَي `memory`/`embeddings` يصف حالة **سابقة**؛ الحالة الحالية = **4 خدمات** (OWUI أساسي، [ADR-025](DECISIONS.md)). هذا القسم (مع [DECISIONS](DECISIONS.md) وتاريخ git) هو **سجلّ التغييرات المعتمد** — لا حاجة لـ CHANGELOG منفصل.

- [x] **تجربة موديل محلّي أكبر (2026-06-29، [ADR-027](DECISIONS.md)):** llama-swap → **موديلان قابلان للاختيار على 6GB** (`Gemma 4` E2B + `Gemma 4 4B` E4B، تبديل في الـ VRAM عند الطلب). **مُتحقَّق حيّاً:** E4B يتّسع (4.76GB/6) وأجاب مباشرةً ("القاهرة")، بينما E2B استنزف التوكنات تفكيراً بلا جواب — دليل عملي على قيمة موديل أكبر قبل قرار Gemini.
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

1. [x] **تقوية P-01 — مكتملة:** ✓ virtual key (بدل master) · ✓ digests الصور الخمس · ✓ max_tokens=2048 · ✓ رصد P-05 · ✓ رؤية · ✓ اختبارات+CI · ✓ توحيد الجذر + GitHub خاص. كلها مُتحقَّقة حيّاً.
2. [↦ فرع] **Context Engine (ذاكرة L2) — متقاعد إلى `future/context-engine` ([ADR-025](DECISIONS.md)).** بُني M0→M4b ومُتحقَّق حيّاً (استرجاع دلالي هجين RRF + حقن في الدردشة + التقاط محادثة)، ثم **استُبدل كمسار أساسي بذاكرة/RAG المدمجة في OWUI**. **لا عمل عليه على master**؛ يُستأنف من الفرع عند مبرّر (موديل أقوى/حجم). المرجع التصميمي: [specs/CONTEXT_ENGINE_V1.md](specs/CONTEXT_ENGINE_V1.md).
3. [ ] **تجهيز تبديل الموديل لـ Gemini** عند النشر (config-only في `litellm-config.yaml` عبر البوّابة — R-ARCH-45 / [ADR-023](DECISIONS.md)).
4. [ ] التخطيط لـ Phase 2 للمنصّة (سحابة/vLLM عند الحاجة).

---

## 4. أهداف Phase 1 — البوّابة + الواجهة (1–10 مستخدمين)

| المعرّف | الهدف | الحالة |
|---|---|---|
| **P-00** | حسم أدوات الجودة وعتباتها وتوثيق المبرّر — [ADR-008](DECISIONS.md). (القرار محسوم؛ إنشاء ملفات الـ scaffolding هو بند "التالي مباشرةً".) | [x] |
| **P-01** | `compose/docker-compose.yml` يشغّل `open-webui` + `litellm` + `llamacpp` + `postgres` بـ `docker compose up`. | [x] **شغّال end-to-end** (4 خدمات healthy، GPU داخل الحاوية، طلب عبر البوّابة نجح، الواجهة على :3000) |
| **P-02** | `litellm-config.yaml`: موديل واحد (Gemma 4 محلي، [ADR-010](DECISIONS.md)) خلف العقد `/v1`؛ managed = تبديل سطر واحد. | [x] |
| **P-03** | `config/env/.env.example` يغطّي كل المفاتيح المطلوبة (لا قيم حقيقية). | [x] |
| **P-04** | منفذ البوّابة غير مكشوف؛ الوصول داخل شبكة Docker فقط (R-ARCH-24). | [x] |
| **P-05** | رصد بحدّ أدنى: كل مسار طلب يُصدر `request_id` + سجلّ كلفة (سياسة الرصد). | [x] **مُتحقَّق حيّاً** (grep واحد عبر litellm+memory) |

## 5. Phase 2+ — صناديق أكبر (محجوز، ليس الآن)

| المعرّف | الهدف | الحالة |
|---|---|---|
| **P-10** | self-host عبر `llama.cpp`/`vLLM` خلف نفس العقد — يفرضه طلب خصوصية/حجم حقيقي. | [ ] |

> لا يُضاف بند Phase 2+ قبل عبور حارس التضخيم ([CONSTITUTION](CONSTITUTION.md) §5) وتسجيل المبرّر في [DECISIONS](DECISIONS.md).

---

## 6. أسئلة / عوائق مفتوحة
> صيغة كل بند: `[OPEN] الوصف — مالكه — أثره`.

- [RESOLVED] **تعارض اسم خدمة LiteLLM:** وُحّد حقل `service` على `litellm` في `ERROR_AND_OBSERVABILITY_POLICY` ليطابق `R-ARCH-31` واسم خدمة Docker (يدعم تتبّع `request_id` عبر الطبقات R-ERR-19).
- [RESOLVED] الـ backend الابتدائي = **موديل Gemma 4 المحلي** (قرار المالك، [ADR-010](DECISIONS.md))؛ managed تبديل سطر واحد لاحقاً.
- [RESOLVED] تشغيل المحرّك = **Docker مع GPU** (قرار المالك، [ADR-011](DECISIONS.md)).
- [RESOLVED] صورة `ghcr.io/ggml-org/llama.cpp:server-cuda` **تدعم gemma4** (master يومي، الدعم منذ إبريل 2026) — لا حاجة لصورة مخصّصة. شرط: تعريف NVIDIA لويندوز يدعم WSL2 GPU + Docker Desktop WSL2.
- [RESOLVED] **تحقّق أوّل تشغيل:** GPU داخل الحاوية مؤكَّد (RTX 4050) + Gemma 4 محمّل بلا "unknown architecture" + healthchecks تعمل (5 خدمات healthy).
- [RESOLVED] **R-ERR-15/16/19 (request_id + service + كلفة بـ JSON):** مُحقَّق فعلياً — `service` يطابق اسم خدمة Docker (litellm/memory)، و`request_id` (litellm_call_id) يمرّ عبر الطبقات، وسطر كلفة per-request يصدر (مُتحقَّق بـ grep حيّ — كود الـ hook + `memory/app.py`).
- [OPEN] أين تُخزَّن الأسرار؟ `.env` محلي الآن مقابل secret manager لاحقاً — Tech Lead — يؤثّر على بنية Compose.
- [OPEN] مُحفِّز self-host الحقيقي (خصوصية/حجم)؟ — Owner — يؤجَّل حتى طلب فعلي (YAGNI).

## 7. أثر القرارات (روابط لـ DECISIONS)
> الكامل في **[DECISIONS](DECISIONS.md)** بصيغة ADR. ملخّص:

| القرار | ملخّص | المرجع |
|---|---|---|
| العقد الثابت | توحيد كل شيء خلف **OpenAI-compatible API** | ADR-001 |
| البوّابة | **LiteLLM** بوّابة مركزية إلزامية | ADR-002 |
| الواجهة | **Open WebUI** متّصلة حصراً بـ LiteLLM | ADR-003 |
| محرّك الاستدلال | **llama.cpp** الآن / **vLLM** لاحقاً (نفس العقد) | ADR-004 |
| التشغيل | **Docker Compose أولاً** | ADR-005 |
| نقطة البدء | موديل managed أولاً (**مُستبدَل بـ ADR-010**) | ADR-006 |
| نطاق المرحلة الأولى | **لا** Kubernetes / SSO / HA / autoscaling (YAGNI) | ADR-007 |
| المحرّك المحلي | **Gemma 4 محلي** على GPU (يستبدل managed-first) | ADR-010/011 |
| اسم الموديل/العلامة | الموديل = "Gemma 4"، الواجهة = "Sankari Chat" | ADR-016/017 |
| الرؤية | تفعيل الصور (mmproj) عبر العقد | ADR-014 |
| التضمين عبر البوّابة | كل تضمين عبر LiteLLM (model-agnostic) | ADR-023 |
| **الحاكم: OWUI أساسي** | اعتماد OWUI RAG+Memory؛ **تقاعد المحرّك المخصّص** إلى فرع | **ADR-025** |
| حوكمة قابلة للتنفيذ + تقوية | فحص ثوابت معمارية في CI + `ENABLE_SIGNUP=false` + نسخ احتياطي | ADR-026 |
| تجربة: موديلان محلّيان | llama-swap (Gemma 4 E2B + 4B قابلان للاختيار على 6GB) | ADR-027 |

---

### كيفية التحديث (تذكير)
- بعد كل خطوة ذات قيمة: انقل البند من القسم 3 → 2، حدّث القسم 1 وتاريخ آخر تحديث.
- قرار **معماري** فقط؟ سجّله كـ ADR في [DECISIONS](DECISIONS.md) ثم أضف صفّاً في القسم 7 (التغييرات غير المعمارية لا تلمس DECISIONS).
- عائق جديد؟ أضفه في القسم 6 بصيغة `[OPEN]`؛ احذفه عند الحلّ.
