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
llm-platform/
├── PROJECT_BLUEPRINT.md     # المخطّط الهندسي المرجعي (استثناء جذر مُصرّح به — R-ARCH-04)
├── compose/
│   └── docker-compose.yml    # تعريف الخدمات الخمس (open-webui, litellm, llamacpp, postgres, memory)
├── config/                  # كل الإعداد الخارجي (لا أسرار قيمية)
│   ├── litellm/
│   │   ├── litellm-config.yaml       # model_list + routing — نقطة التبديل الوحيدة
│   │   └── memory_hook.py            # hook الذاكرة per-user (يعمل داخل عملية litellm)
│   └── env/
│       └── .env.example              # قالب المتغيّرات (placeholders فقط، بلا قيم حقيقية)
├── services/                # كود خدماتنا المحاواة (أُنشئ بـ ADR-012/013)
│   └── memory/              # خدمة الذاكرة per-user (FastAPI + asyncpg)
├── research/                # أبحاث داعمة للقرارات (MEMORY_LANDSCAPE, VISION_SETUP) — معفاة من حدّ 180 سطر
├── scripts/                 # سكربتات تشغيل/صيانة (عند الحاجة)
├── docs/                    # كل وثائق الحوكمة (هذا الملف وإخوته)
│   ├── CONSTITUTION.md
│   ├── ARCHITECTURE_RULES.md
│   ├── ERROR_AND_OBSERVABILITY_POLICY.md
│   ├── DECISIONS.md
│   └── PROGRESS_MAP.md
├── models/                  # ملفات GGUF (git-ignored، كبيرة)
├── .gitignore
└── README.md
```

> **قرار هيكلي:** إعادة تنظيم المستودع إلى `compose/` + `config/` + `docs/`، وتوحيد كل وثائق الحوكمة تحت `llm-platform/docs/`، **يُسجَّل كـ ADR** في [DECISIONS](DECISIONS.md) قبل اعتماده كحالة فعلية. حتى ذلك الحين هذا الجدول هو الهدف المرجعي.

- **R-ARCH-01** — لكل مجلد جذري **مسؤولية واحدة** كما في الجدول. ممنوع خلط نوعين (لا `*.yaml` إعداد داخل `compose/`، ولا compose داخل `config/`). فحص: مراجعة المسار مقابل الجدول.
- **R-ARCH-02** — `models/`، `config/env/.env`، وأي `*.override.yml` محلي **مُدرَجة في `.gitignore`** ولا تُرفع أبداً. فحص CI: `git ls-files | grep -E '(^models/|\.env$)'` يجب أن يعيد فراغاً.
- **R-ARCH-03** — لا ملفات إعداد أو أسرار في جذر المستودع عدا المُصرّح بها: `.gitignore`، `README.md`، `PROJECT_BLUEPRINT.md`. كل إعداد آخر مكانه `config/`. فحص: قائمة الجذر مقابل هذه القائمة البيضاء.
- **R-ARCH-04** — كل وثائق الحوكمة تحت `docs/` فقط؛ الروابط المتبادلة بينها **نسبية ومجاورة** (`./X.md`). فحص: link-checker لا يجد رابطاً معطّلاً (dangling).
- **R-ARCH-05** — أي ملف وثيقة هندسية **< 180 سطراً** (حدّ صارم؛ CI يفشل عند 180 فأكثر). تجاوز ذلك يستوجب التقسيم. الإيجاز فضيلة.

> `services/` أُنشئ فعلاً (خدمة `memory`، [ADR-012](DECISIONS.md)/[ADR-013](DECISIONS.md))؛ `infra/` **لا يُنشأ الآن** (YAGNI، يُنشأ بقرار ADR عند الحاجة).

---

## 2. الطبقات واتجاه الاعتماد (Layering)

تدفّق وحيد الاتجاه: `Frontend → Gateway → Engine → Model`. لا قفز للطبقات ولا اعتماد عكسي.

```text
open-webui ──/v1──▶ litellm ──/v1──▶ llamacpp (→ vLLM لاحقاً) ──▶ GGUF model
 (frontend)         (gateway)         (engine)
```

- **R-ARCH-10** — **العميل لا يعرف المحرّك.** أي frontend / app / agent / script يتّصل **حصراً** بعنوان البوّابة (`http://litellm:4000/v1`). فحص: `api_base`/`base_url` في أي عميل = منفذ البوّابة فقط، لا منفذ المحرّك (`llamacpp:8000`).
- **R-ARCH-11** — الاتصال **وحيد الاتجاه نزولاً** فقط. ممنوع أن يستدعي المحرّك البوّابة، أو تستدعي البوّابة الواجهة. فحص: مراجعة `depends_on` وعناوين URL في `docker-compose.yml`.
- **R-ARCH-12** — **ممنوع تجاوز طبقة** (layer skipping): الواجهة لا تكلّم المحرّك مباشرةً. كل عبور يمرّ بالطبقة المجاورة عبر عقدها.
- **R-ARCH-13** — **العقد بين الطبقات هو `OpenAI-compatible API` حصراً** (`/v1/chat/completions`, `/v1/completions`, `/v1/embeddings`, `/v1/models`). أي تكامل لا يتكلّم هذا العقد يُرفض (تجسيد ADR-001).
- **R-ARCH-14** — استبدال أي طبقة (`open-webui`↔بديل، `llamacpp`↔vLLM، محلي↔managed) يجب أن **لا يلمس الطبقات الأخرى**. فحص ميكانيكي: تبديل المحرّك = diff يلمس `config/litellm/litellm-config.yaml` فقط (ولا ملف آخر).

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
- **R-ARCH-31** — **أسماء خدمات Docker حياديّة المزوّد وصريحة الدور:** `open-webui`, `litellm`, `llamacpp`, `postgres`, `memory` (أُضيفت بـ [ADR-012](DECISIONS.md)/[ADR-013](DECISIONS.md)). ممنوع أسماء غامضة (`app`, `server`, `svc1`) أو أسماء دور عامة (`gateway`, `engine`, `webui`, `db`). فحص: مفاتيح `services:` في `docker-compose.yml` ⊆ هذه القائمة. (مثال البلوبرنت §10.2 يستخدم حالياً `engine/gateway/webui/db` ويجب تصحيحه لمطابقة هذه القاعدة — يُحسم بـ ADR.)
- **R-ARCH-32** — **متغيّرات البيئة:** `SCREAMING_SNAKE_CASE` ببادئة المكوّن: `LITELLM_*`, `WEBUI_*`, `DATABASE_URL`. تتطابق حرفياً مع `config/env/.env.example`.
- **R-ARCH-33** — **أسماء الموديلات في `model_list`:** اسم **حياديّ تجاه المحرّك** (لا اسم محرّك ولا مسار ملف) كي يبقى التبديل خلفه شفّافاً للعميل. مثال منطقي: `local-chat`, `embed-default`؛ ويجوز اسم علامة منتج حياديّ تجاه المحرّك مثل `Sankari Chat` ([ADR-016](DECISIONS.md)). فحص: الاسم لا يذكر المحرّك/الموديل/المسار.
- **R-ARCH-34** — حقل `service` في كل log/خطأ (R-ERR-05) **يطابق حرفياً اسم خدمة Docker** المعتمدة في R-ARCH-31 (`litellm`، لا `litellm-gateway`)؛ كي يعمل تتبّع `request_id` عبر الطبقات بـ grep واحد (R-ERR-25).

---

## 5. Config-driven & 12-Factor

- **R-ARCH-40** — **فصل تام بين الإعداد والكود (12-factor III).** كل ما يختلف بين البيئات (اسم الموديل، `api_base`، المفاتيح، حجم السياق، الحصص) من `env`/`config/`، لا hardcoded. فحص: grep على القيم المتغيّرة داخل الكود/الصورة = فراغ.
- **R-ARCH-41** — **صورة واحدة غير قابلة للتعديل (immutable):** كل اختلاف سلوكي يأتي من الحقن الخارجي وقت التشغيل، لا من إعادة بناء الصورة. (مسار البيئات المتعدّدة يُقرّر بـ ADR عند الحاجة، لا يُستبق.)
- **R-ARCH-42** — **`.env.example` فقط** مُتتبَّع في git، يحوي **كل** المفاتيح المطلوبة بقيم placeholder. `.env` الفعلي git-ignored بصلاحيات مقيّدة (`600`). فحص: تطابق مفاتيح `.env.example` مع كل مراجع `${...}` في الإعداد.
- **R-ARCH-43** — الأسرار في Phase 1 من `.env` فقط، عبر حقن بيئة قياسي بلا منطق قراءة خاص بمزوّد داخل التطبيق. مسار الترقية لمدير أسرار يُقرّر بـ ADR لاحق.
- **R-ARCH-44** — `LITELLM_SALT_KEY` يُضبط منذ اليوم الأول ولا يُغيّر بعد تخزين بيانات اعتماد (تغييره يعطّل فكّ التشفير). يُوثّق هذا القيد بجوار تعريفه في `.env.example`.
- **R-ARCH-45** — تبديل المحرّك أو المزوّد = تعديل **سطر `api_base` واحد** في `config/litellm/litellm-config.yaml`، دون لمس أي كود عميل. فحص (R-ARCH-14): الـ PR diff لا يلمس سوى هذا الملف.

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
- [ ] تبديل المحرّك = diff يلمس `litellm-config.yaml` فقط؟ (R-ARCH-14/45)
