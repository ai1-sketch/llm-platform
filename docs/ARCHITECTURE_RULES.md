# Architecture Rules — قوانين المعمارية والحدود

> وثيقة حاكمة لبنية مستودع `llm-platform`: المجلدات، اتجاه الاعتماد، الاستيراد/الحدود، التسمية، و config-driven. كل قاعدة `R-ARCH-NN` **قابلة للفحص** من مراجِع بشري أو linter / CI.
>
> **يُقرأ مع:** [CONSTITUTION](CONSTITUTION.md) · [ERROR_AND_OBSERVABILITY_POLICY](ERROR_AND_OBSERVABILITY_POLICY.md) · [DECISIONS](DECISIONS.md) · [PROGRESS_MAP](PROGRESS_MAP.md) · [../PROJECT_BLUEPRINT.md](../PROJECT_BLUEPRINT.md)
>
> المبدأ الحاكم: **"نفس الشكل، صناديق أكبر"** — العقد `OpenAI-compatible API` ثابت؛ المحرّك خلف البوّابة تفصيل قابل للاستبدال. ابدأ بسيطاً (YAGNI) واترك مكاناً للتوسّع دون إعادة بناء.
>
> النطاق: Phase 1 فقط (`docker-compose`، single-node، 1–10 مستخدمين). ما يتجاوز ذلك يُقرّر بـ ADR في [DECISIONS](DECISIONS.md)، لا يُستبق هنا.

---

## 1. هيكل المستودع (Repo Layout)

```text
<repo-root>  (= المنصّة؛ رُقِّيت من llm-platform/ — ADR-018)
├── CLAUDE.md                # عقد المساعد (auto-loaded)
├── PROJECT_BLUEPRINT.md     # المخطّط الهندسي المرجعي
├── README.md                # مدخل بشري + خريطة الحوكمة
├── pyproject.toml           # أدوات الجودة (Ruff — ADR-008)
├── .pre-commit-config.yaml  # مرآة فحوص CI
├── .gitignore
├── .github/workflows/ci.yml # بوّابة CI (ruff + gitleaks + تحقّق compose)
├── compose/
│   └── docker-compose.yml   # تعريف الخدمات الخمس (open-webui, litellm, vllm, postgres-litellm, postgres-openwebui) — ADR-025/028/030
├── config/                  # كل الإعداد الخارجي (لا أسرار قيمية)
│   ├── litellm/
│   │   └── litellm-config.yaml   # model_list + routing — نقطة التبديل الوحيدة
│   ├── vllm/
│   │   └── vllm-config.yaml      # إعداد المحرّك: الموديل + معاملات الذاكرة/السياق (ADR-028)
│   ├── postgres/
│   │   ├── litellm-init/         # تهيئة نسخة postgres-litellm: دور/قاعدة + عزل (ADR-029/030)
│   │   └── openwebui-init/       # تهيئة نسخة postgres-openwebui: دور/قاعدة + عزل + امتداد vector (ADR-029/030)
│   └── env/
│       └── .env.example          # قالب المتغيّرات (placeholders فقط)
├── docs/                    # كل وثائق الحوكمة (هذا الملف وإخوته)
│   ├── CONSTITUTION.md · ARCHITECTURE_RULES.md · ERROR_AND_OBSERVABILITY_POLICY.md
│   ├── DECISIONS.md · PROGRESS_MAP.md
│   └── specs/CONTEXT_ENGINE_V1.md   # مواصفة محرّك السياق المتقاعد (مرجع، ADR-025)
├── research/               # أبحاث داعمة (CONTEXT_ENGINE_RATIONALE, MEMORY_LANDSCAPE, VISION_SETUP) — معفاة من حدّ 180 سطر
├── legacy/                 # النموذج الأولي المؤرشَف (Qwen3/Gemma، غير مُشغَّل، خارج البوّابة)
└── models-gemma4/          # بقايا GGUF من عهد llama.cpp (git-ignored؛ لم تعد تُستخدم بعد ADR-028 — حذفها قرار مالك)
```

> **قرار هيكلي ([ADR-018](DECISIONS.md)):** المنصّة في **جذر المستودع** (رُقِّيت من `llm-platform/`)، والنموذج الأولي القديم مؤرشَف في `legacy/` (متتبَّع، خارج البوّابة). هذا الجدول يعكس الحالة الفعلية المعتمدة.

- **R-ARCH-01** — لكل مجلد جذري **مسؤولية واحدة** كما في الجدول. ممنوع خلط نوعين (لا `*.yaml` إعداد داخل `compose/`، ولا compose داخل `config/`). فحص: مراجعة المسار مقابل الجدول.
- **R-ARCH-02** — `models/`، `config/env/.env`، وأي `*.override.yml` محلي **مُدرَجة في `.gitignore`** ولا تُرفع أبداً. فحص CI: `git ls-files | grep -E '(^models/|\.env$)'` يجب أن يعيد فراغاً.
- **R-ARCH-03** — جذر المستودع يحوي فقط: وثائق الحوكمة العليا (`CLAUDE.md`، `PROJECT_BLUEPRINT.md`، `README.md`)، إعداد الأدوات (`pyproject.toml`، `.pre-commit-config.yaml`، `.gitignore`، `.editorconfig`)، ملفّات المشروع المعيارية (`LICENSE`)، و`.github/` (تحوي `SECURITY.md`، `CONTRIBUTING.md`، `CODEOWNERS`، `workflows/`). **لا أسرار** في الجذر؛ كل إعداد تطبيقي مكانه `config/`. فحص: قائمة الجذر مقابل هذه القائمة البيضاء (ADR-018).
- **R-ARCH-04** — كل وثائق الحوكمة تحت `docs/` فقط؛ الروابط المتبادلة بينها **نسبية ومجاورة** (`./X.md`). فحص: link-checker لا يجد رابطاً معطّلاً (dangling).
- **R-ARCH-05** — وثائق الحوكمة **الأساسية** (CONSTITUTION · ARCHITECTURE_RULES · ERROR_AND_OBSERVABILITY_POLICY · PROGRESS_MAP) يُستحسن أن تكون **< 180 سطراً** (إرشادي بمراجعة بشرية — Ruff بلا قاعدة طول-ملف، [ADR-008](DECISIONS.md)؛ لا بوّابة CI). الإيجاز فضيلة، والتجاوز يستوجب التقسيم. **مُعفى:** سجلّ ADR ([DECISIONS](DECISIONS.md)، ينمو append-only) · `docs/specs/` · `research/` · [PROJECT_BLUEPRINT](../PROJECT_BLUEPRINT.md) (مرجع موسوعي).

> `services/` و`tests/` (خدمة `memory` + اختباراتها) **متقاعدة إلى فرع `future/context-engine`** ([ADR-025](DECISIONS.md))؛ المسار الأساسي بلا كود بايثون. `infra/` لا يُنشأ الآن (YAGNI).

---

## 2. الطبقات واتجاه الاعتماد (Layering)

تدفّق وحيد الاتجاه: `Frontend → Gateway → Engine → Model`. لا قفز للطبقات ولا اعتماد عكسي.

```text
open-webui ──/v1──▶ litellm ──/v1──▶ vllm (llama.cpp سابقاً — ADR-028) ──▶ HF model
 (frontend)         (gateway)         (engine)
```

- **R-ARCH-10** — **العميل لا يعرف المحرّك.** أي frontend / app / agent / script يتّصل **حصراً** بعنوان البوّابة (`http://litellm:4000/v1`). فحص: `api_base`/`base_url` في أي عميل = منفذ البوّابة فقط، لا منفذ المحرّك (`vllm:8000`). **يشمل ذلك التضمين** (القاعدة تبقى سارية لأي عميل/تكامل). مثال محرّك السياق (`memory`→`embed-default` عبر البوّابة، [ADR-023](DECISIONS.md)) متقاعد إلى فرع `future/context-engine` ([ADR-025](DECISIONS.md)).
- **R-ARCH-11** — الاتصال **وحيد الاتجاه نزولاً** فقط. ممنوع أن يستدعي المحرّك البوّابة، أو تستدعي البوّابة الواجهة. فحص: مراجعة `depends_on` وعناوين URL في `docker-compose.yml`.
- **R-ARCH-12** — **ممنوع تجاوز طبقة** (layer skipping): الواجهة لا تكلّم المحرّك مباشرةً. كل عبور يمرّ بالطبقة المجاورة عبر عقدها.
- **R-ARCH-13** — **العقد بين الطبقات هو `OpenAI-compatible API` حصراً** (`/v1/chat/completions`, `/v1/completions`, `/v1/embeddings`, `/v1/models`). أي تكامل لا يتكلّم هذا العقد يُرفض (تجسيد ADR-001).
- **R-ARCH-14** — استبدال أي طبقة (`open-webui`↔بديل، `vllm`↔بديل (llama.cpp/SGLang)، محلي↔managed) يجب أن **لا يلمس الطبقات الأخرى**. فحص ميكانيكي: تبديل المزوّد/الوجهة خلف البوّابة = diff يلمس `config/litellm/litellm-config.yaml` فقط؛ استبدال المحرّك نفسه (صورة/خدمة) يلمس compose + config المحرّك ويستلزم ADR (كما ADR-027/028) — دون مساس بالواجهة أو عقد `/v1`.

---

## 3. الاستيراد والحدود (Imports & Boundaries)

- **R-ARCH-20** — **لا أسرار في الكود أو الصور (images) أو ملفات الإعداد المُتتبَّعة.** القيم الحسّاسة تُحقَن وقت التشغيل من البيئة فقط. فحص محدّد: secret-scanner (مثل `gitleaks`) في CI، أو grep على الأنماط المعدودة `sk-`, `AKIA`, `-----BEGIN`, `password=` في الملفات المتتبَّعة = فراغ.
- **R-ARCH-21** — `litellm-config.yaml` يشير للأسرار **بالمرجع فقط** عبر استبدال متغيّرات بيئة (`${LITELLM_MASTER_KEY}`)، لا بقيمة نصّية صريحة. فحص: لا سلاسل تطابق أنماط R-ARCH-20 داخل الملف.
- **R-ARCH-22** — لا ربط بمزوّد/سحابة محدّدة داخل الكود أو الصورة (`region`, أسماء buckets, ARNs, أنواع instances صلبة). مكانها متغيّرات بيئة الآن، و`infra/` عند إنشائه لاحقاً (Vendor-neutrality).
- **R-ARCH-23** — `compose/` لا يحوي منطق تطبيق؛ `config/` لا يحوي تنفيذاً؛ `scripts/` لا يحوي أسراراً قيمية. كل مجلد لا يتجاوز حدّ مسؤوليته (R-ARCH-01).
- **R-ARCH-24** — **البوّابة لا تُكشف للإنترنت العام.** الخدمة الوحيدة المسموح لها بـ `ports:` على واجهة عامة هي `open-webui` (نقطة دخول المستخدم). يجوز ربط `litellm` على `127.0.0.1` محلياً للتشخيص؛ ممنوع ربطها على `0.0.0.0`/واجهة عامة. فحص: مراجعة كل `ports:` في `docker-compose.yml`.

---

## 4. اصطلاحات التسمية (Naming)

- **R-ARCH-30** — **الملفات والمجلدات:** `kebab-case` (مثل `litellm-config.yaml`). الاستثناء الوحيد: الوثائق بصيغة `SCREAMING_SNAKE_CASE.md`.
- **R-ARCH-31** — **أسماء خدمات Docker حياديّة المزوّد وصريحة الدور:** `open-webui`, `litellm`, `vllm`, `postgres-litellm`, `postgres-openwebui` (5 خدمات؛ المحرّك `vllm` منذ [ADR-028](DECISIONS.md)؛ قاعدتا postgres مخصّصتان — نسخة لكل تطبيق — منذ [ADR-030](DECISIONS.md)؛ `memory`/`embeddings` متقاعدتان إلى فرع `future/context-engine` بعد [ADR-025](DECISIONS.md)). ممنوع أسماء غامضة (`app`, `server`, `svc1`) أو أسماء دور عامة (`gateway`, `engine`, `webui`, `db`). فحص: مفاتيح `services:` في `docker-compose.yml` ⊆ هذه القائمة (مفروض آلياً في CI — `check_invariants.py`). **مُحلّ:** مقاطع PROJECT_BLUEPRINT §10.2 تستخدم أسماء توضيحية (`engine/gateway/webui/db`)، وقد وُسِمت صراحةً كأمثلة إيضاحية مع الإشارة للأسماء المعتمدة ومصدر الحقيقة (`compose/docker-compose.yml`) — فلا تناقض فعليّاً مع القاعدة.
- **R-ARCH-32** — **متغيّرات البيئة:** `SCREAMING_SNAKE_CASE` ببادئة المكوّن: `LITELLM_*`, `WEBUI_*`, `DATABASE_URL`. تتطابق حرفياً مع `config/env/.env.example`.
- **R-ARCH-33** — **أسماء الموديلات في `model_list`:** `model_name` لصيقة عرض/منتج يختارها المالك (قد تكون اسم الموديل الفعلي مثل `Qwen3 4B`، أو اسماً منطقياً مثل `local-chat`) — [ADR-017](DECISIONS.md). **حياديّة التبديل تُصان على مستوى الكود/العقد** (العميل يستهدف `api_base` للبوّابة بلا كود خاص بمحرّك — R-ARCH-10/14)، لا على مستوى اللصيقة؛ فإن ذكرت اللصيقة الموديل تُحدَّث عند التبديل (سطر واحد). فحص: لا كود عميل يربط بمحرّك بعينه.
- **R-ARCH-34** — حقل `service` في كل log/خطأ (R-ERR-05) **يطابق حرفياً اسم خدمة Docker** المعتمدة في R-ARCH-31 (`litellm`، لا `litellm-gateway`)؛ كي يعمل تتبّع `request_id` عبر الطبقات بـ grep واحد (R-ERR-19).

---

## 5. Config-driven & 12-Factor

- **R-ARCH-40** — **فصل تام بين الإعداد والكود (12-factor III).** كل ما يختلف بين البيئات (اسم الموديل، `api_base`، المفاتيح، حجم السياق، الحصص) من `env`/`config/`، لا hardcoded. فحص: grep على القيم المتغيّرة داخل الكود/الصورة = فراغ.
- **R-ARCH-41** — **صورة واحدة غير قابلة للتعديل (immutable):** كل اختلاف سلوكي يأتي من الحقن الخارجي وقت التشغيل، لا من إعادة بناء الصورة. (مسار البيئات المتعدّدة يُقرّر بـ ADR عند الحاجة، لا يُستبق.)
- **R-ARCH-42** — **`.env.example` فقط** مُتتبَّع في git، يحوي **كل** المفاتيح المطلوبة بقيم placeholder. `.env` الفعلي git-ignored بصلاحيات مقيّدة (`600`). فحص: تطابق مفاتيح `.env.example` مع كل مراجع `${...}` في الإعداد.
- **R-ARCH-43** — الأسرار في Phase 1 من `.env` فقط، عبر حقن بيئة قياسي بلا منطق قراءة خاص بمزوّد داخل التطبيق. مسار الترقية لمدير أسرار يُقرّر بـ ADR لاحق.
- **R-ARCH-44** — `LITELLM_SALT_KEY` يُضبط منذ اليوم الأول ولا يُغيّر بعد تخزين بيانات اعتماد (تغييره يعطّل فكّ التشفير). يُوثّق هذا القيد بجوار تعريفه في `.env.example`.
- **R-ARCH-45** — تبديل **المزوّد/الوجهة خلف البوّابة** (محلي↔managed، موديل↔موديل عبر نفس المحرّك) = تعديل `config/litellm/litellm-config.yaml` (و/أو config المحرّك) **فقط**، دون لمس أي كود عميل أو طبقة أخرى. أمّا **استبدال المحرّك نفسه** (صورة/خدمة) فيلمس compose + config المحرّك ويستلزم ADR — كما R-ARCH-14 وسابقتا ADR-027/028. فحص: الـ PR diff لا يلمس كود عميل/واجهة في الحالتين.

---

## قائمة تحقّق سريعة (Review Gate)

- [ ] المجلدات ضمن مسؤولياتها، ولا ملف غير مُصرّح به في الجذر؟ (R-ARCH-01/03/23)
- [ ] كل وثائق الحوكمة تحت `docs/` وروابطها غير معطّلة؟ (R-ARCH-04)
- [ ] لا أسرار/`models/` في git (scanner أخضر)؟ (R-ARCH-02/20/42)
- [ ] العميل يكلّم البوّابة فقط، اتجاه واحد، بلا تجاوز طبقات؟ (R-ARCH-10/11/12)
- [ ] العقد `OpenAI /v1` بين كل طبقتين؟ (R-ARCH-13)
- [ ] فقط `open-webui` مكشوفة؛ البوّابة غير مكشوفة للإنترنت العام؟ (R-ARCH-24)
- [ ] أسماء الخدمات حياديّة وحقل `service` يطابقها؟ (R-ARCH-31/34)
- [ ] كل متغيّر بيئي في `.env.example`، ولا hardcoding؟ (R-ARCH-40/42)
- [ ] تبديل المزوّد/الوجهة = diff في config فقط (بلا كود عميل)؛ واستبدال المحرّك = ADR + compose/config المحرّك فقط؟ (R-ARCH-14/45)
