# Error & Observability Policy

> سياسة الأخطاء والرصد لمنصّة `llm-platform`. تُقرأ مع [CONSTITUTION](CONSTITUTION.md) · [ARCHITECTURE_RULES](ARCHITECTURE_RULES.md) · [DECISIONS](DECISIONS.md) · [PROGRESS_MAP](PROGRESS_MAP.md).
>
> **الحالة:** نافذة v1 (مُعتمدة ومُلزِمة) · **Owner:** SRE · **النطاق (Phase 1):** المنصّة الفعلية — موديل محلي (vllm/GPU، [ADR-028](DECISIONS.md)) خلف LiteLLM + Open WebUI (تملك RAG + Memory، [ADR-025](DECISIONS.md)) + قاعدتَي postgres مخصّصتين ([ADR-030](DECISIONS.md)).

العقيدة المركزية: **"الخطأ يبلّغ عن نفسه" (errors that announce themselves).** كل فشل يخبرنا فوراً: **ماذا حدث، في أي طلب، وكيف نصلحه**. الفشل صاخب وواضح، لا صامت ولا غامض.

**نطاق الإلزام (مهم):** المكوّنات الأساسية (LiteLLM, Open WebUI) صور (images) جاهزة لا نملك شيفرتها الداخلية:

| الفئة | ما يُفرَض | المرجع |
|---|---|---|
| كودنا (`scripts/`، أي adapter لاحق) | كل القواعد أدناه قابلة للفحص بـ linter / code review | §1, §2, §3 |
| الخدمات الجاهزة (`litellm`, `open-webui`, `vllm`, قاعدتا postgres) | ضبط `config` فقط: مستوى السجل، JSON، healthcheck، تمرير `request_id` | §4, §5 |

القواعد محدَّدة لـ Phase 1. التوسّع لاحقاً (taxonomy كامل، readiness تفصيلي) **نفس الشكل، صناديق أكبر** — يُضاف عند كتابة أول adapter فعلي، ويُتتبَّع في [PROGRESS_MAP](PROGRESS_MAP.md).

---

## 1) Fail-fast عند بدء الإعداد (Startup validation)

- **R-ERR-01** أي script/adapter نكتبه **يتحقق من إعداده قبل أي عمل**. إعداد غير صالح ⇒ خروج بكود `!= 0` فوراً مع خطأ مهيكل (§2). ممنوع المتابعة "ناقصاً".
- **R-ERR-02** المتغيرات الإلزامية (`LITELLM_MASTER_KEY`, `*_API_KEY`, ports) تُفحص صراحةً؛ الناقص ⇒ خطأ يسمّي **اسم المتغير** المفقود بالحرف.
- **R-ERR-03** فشل الإعداد يطبع خطأً واحداً مهيكلاً ثم يخرج. ممنوع loop إعادة محاولة صامت على إعداد خاطئ (config لا يُصلح نفسه).

> probe الاعتماديات الحرجة و `/ready` التفصيلي **مؤجّلان** حتى يوجد inference engine محلي نملك كوده (ADR-004/006) — مُتتبَّع في [PROGRESS_MAP](PROGRESS_MAP.md). صحّة الخدمات الجاهزة تُعتمد عبر `healthcheck` في `docker-compose.yml` (§4).

---

## 2) بنية الخطأ الموحّدة (Unified error shape)

ينطبق على أي خطأ يصدر **من كودنا** (adapter / script).

- **R-ERR-04** الحقول **الإلزامية الثلاثة** في كل خطأ من كودنا:

| الحقل | المعنى |
|---|---|
| `code` | كود من الـ taxonomy (مؤجّل، انظر §3)، مثل `CONFIG_MISSING_KEY` |
| `message` | رسالة بشرية واضحة، بدون أسرار |
| `request_id` | معرّف الطلب/الترابط (§5) |

- **R-ERR-05** `service` و `remediation` **مستحسنان** (best-effort)؛ و `location` (`module.func:line`) **في الـ logs فقط** best-effort — لا يُفرَض في عقد العميل (هشّ ويتكسّر مع كل refactor).
- **R-ERR-06** **العقد الخارجي = OpenAI-compatible** (ADR-001). الردود للعميل تلتزم شكل خطأ OpenAI `{"error": {...}}` مع HTTP status صحيح. حقل `type` **مطلوب بعقد OpenAI** ويُضاف بجانب الحقول الداخلية دون كسر العقد.
- **R-ERR-07** ممنوع تسريب الأسرار/المفاتيح/الـ stack الكامل في `message` المُعاد للعميل. التفاصيل الكاملة في الـ logs فقط، مربوطة بنفس `request_id` (§5).

### مثال ملموس

**خطأ سيّئ (مرفوض):**
```
ERROR: request failed
```
لا code، لا request_id، لا حلّ. عديم القيمة — يجبر المحقّق على قراءة الكود.

**خطأ جيّد (مطلوب):**
```json
{
  "error": {
    "code": "UPSTREAM_MODEL_UNAVAILABLE",
    "message": "Routing to model 'local-chat' failed: connection refused.",
    "type": "service_unavailable",
    "service": "litellm",
    "request_id": "req_01HX9...",
    "remediation": "تحقّق من api_base لهذا الموديل في config/litellm/litellm-config.yaml."
  }
}
```
> الإلزامي هنا `code` + `message` + `request_id`، و `type` لعقد OpenAI (R-ERR-06). البقية (`service`, `remediation`) best-effort.

---

## 3) منع الالتقاط الصامت (No silent catch)

ينطبق على كودنا، ويُفرَض في CI.

- **R-ERR-08** ممنوع `except: pass` أو `catch {}` فارغ، وممنوع ابتلاع الاستثناء دون تسجيل أو إعادة رفع. كل استثناء إمّا (a) يُعالَج بمعنى واضح، أو (b) يُسجَّل ويُعاد رفعه — لا ثالث.
- **R-ERR-09** ممنوع `except Exception` عام يُخفي السبب. التقط النوع المحدّد؛ وإن لزم العام، سجّله بـ `code` + السياق ثم أعِد الرفع.
- **R-ERR-10** ممنوع تحويل الخطأ إلى نجاح زائف (`200`/قيمة فارغة بدل خطأ). الفشل يبقى مرئياً للأعلى.
- **R-ERR-11 (CI/lint)** linter يرفض الـ catch الفارغ والـ bare-except. مخالفة §3 = build أحمر.

> **Taxonomy (مؤجّل):** مصدر الحقيقة الوحيد لجدول الأكواد = `scripts/errors.py` (يُنشأ مع أول adapter). prefixes أوّلية للاسترشاد: `CONFIG_*`, `AUTH_*`, `VALIDATION_*`, `RATE_LIMIT_*`, `UPSTREAM_*`, `TIMEOUT_*`, `INTERNAL_*` (ربط `4xx`=خطأ المتصل / `5xx`=خطؤنا). لا يُفصَّل قبل وجود كود يستهلكه (CONSTITUTION §5) — مُتتبَّع في [PROGRESS_MAP](PROGRESS_MAP.md).

---

## 4) Health & Readiness (Phase 1 = config فقط)

- **R-ERR-12** الخدمات الجاهزة لها endpoints صحّة خاصّة بها؛ **لا نكتبها**. واجبنا ربطها في `compose/docker-compose.yml` كـ `healthcheck` لكل خدمة، ليظهر الفشل في `docker compose ps`.
- **R-ERR-13** تمييز liveness عن readiness و `/ready` بفحص اعتماديات **يُكتب فقط عند وجود adapter / inference engine محلي نملك كوده** — مؤجّل ([PROGRESS_MAP](PROGRESS_MAP.md)).

---

## 5) التسجيل المهيكل (Structured JSON logging)

- **R-ERR-14** سجلّ **LiteLLM** (موضع الرصد الحرج) = **JSON سطر واحد** عبر `json_logs` (`timestamp` UTC، `level`، `request_id`=litellm_call_id، `message`، + سطر الكلفة). بقيّة الصور الجاهزة (`open-webui`، `vllm`، قاعدتا postgres) تُصدر سجلّها النصّي الخاص بمستوى مضبوط — **استثناء موثّق لـ JSON** (لا نملك شيفرتها لنفرض شكلها؛ تُربَط بالحاوية + الطابع الزمني). حقل `service` (=اسم خدمة Docker) والأكواد المهيكلة يُفرَضان على **كودنا** حين يوجد adapter — لا كود لنا على المسار حالياً ([ADR-025](DECISIONS.md)).
- **R-ERR-15** **Correlation/Request ID:** على master الحالي يُلتقط **عند البوّابة** (LiteLLM يولّد `litellm_call_id`، يظهر في سجلّها + سطر الكلفة). **التمرير الكامل عبر الطبقات** (OWUI→LiteLLM→vLLM عبر header `X-Request-ID`) **مؤجَّل** حتى وجود adapter نملك كوده على المسار — أُثبت سابقاً بخدمة `memory` المتقاعدة ([ADR-025](DECISIONS.md))، يُستأنف من فرع `future/context-engine`؛ مُتتبَّع في [PROGRESS_MAP](PROGRESS_MAP.md).
- **R-ERR-16** قيمة حقل `service` تطابق **اسم خدمة Docker** المعتمد في `docker-compose.yml` (R-ARCH-31): `open-webui`, `litellm`, `vllm`, `postgres-litellm`, `postgres-openwebui` (5 خدمات؛ المحرّك `vllm` منذ [ADR-028](DECISIONS.md)؛ قاعدتان مخصّصتان منذ [ADR-030](DECISIONS.md)؛ `memory`/`embeddings` متقاعدتان إلى فرع `future/context-engine` بعد [ADR-025](DECISIONS.md)؛ `prometheus`/`grafana` بنية مراقبة **خارج مسار الطلب** فلا تُصدر حقل `service` — [ADR-031](DECISIONS.md)/[ADR-033](DECISIONS.md)). الخدمات صور جاهزة بسجلّها: `litellm` JSON عبر config (`json_logs`) وهي **موضع الرصد الحرج** (request_id + الكلفة عند البوّابة)؛ و`open-webui` و`vllm` وقاعدتا postgres تُصدر سجلّها النصّي الخاص بمستوى مضبوط — **استثناء موثّق لـ R-ERR-14** (صور لا نملك شيفرتها، ولا تُصدر حقل `service` قابلاً للضبط). لذا على master الحالي تطابق حقل `service` عبر **كل** الطبقات **غير محقَّق** (يُقارَب بالربط باسم الحاوية + الطابع الزمني)؛ يكتمل مع أوّل adapter نملكه — شرط R-ERR-19 المؤجَّل.
- **R-ERR-17** المستويات: `DEBUG`, `INFO` (افتراضي), `WARN`, `ERROR` (فشل طلب), `CRITICAL` (فشل يهدّد الخدمة). يُضبط عبر config.
- **R-ERR-18** ممنوع طباعة الأسرار/محتوى المستخدم الحسّاس في السجل؛ المفاتيح تُقنَّع (`sk-...abcd`). السجل يخرج إلى `stdout`/`stderr` فقط (عقد الحاويات)، لا إلى ملفات داخل الحاوية.

---

## 6) الفشل الصاخب + سرعة الالتقاط (Fail loud, find fast)

- **R-ERR-19** **معيار النجاح (Phase 1):** بمعرفة `request_id` يصل المحقّق إلى السطر الجذري في سجلّ **LiteLLM** (موضع الرصد الحرج) بأمر `grep` واحد. **الانتشار الكامل عبر كل الطبقات** (OWUI/vLLM) **مؤجَّل** حتى وجود adapter نملك كوده — أُثبت سابقاً بخدمة `memory` المتقاعدة ([ADR-025](DECISIONS.md))؛ مُتتبَّع في [PROGRESS_MAP](PROGRESS_MAP.md).
- **R-ERR-20** كل سطر `ERROR` يحوي `code` + `message` كافياً ليبدأ الإصلاح **دون قراءة الكود**. سطر خطأ يتطلّب فتح المصدر لفهمه = سطر خطأ فاشل.
- **R-ERR-21** **الفشل الصاخب:** عند خطأ غير متوقّع، يُسجَّل `ERROR`/`CRITICAL` مهيكل ويُرفض الطلب بوضوح — لا تدهور صامت ولا نتيجة جزئية مضلِّلة.

---

## قائمة تحقّق المراجعة (Reviewer checklist)

- [ ] إعداد غير صالح ⇒ فشل بدء واضح يسمّي المتغير (§1).
- [ ] كل خطأ من كودنا يحوي `code` + `message` + `request_id` (+`type` للعميل) (§2 / R-ERR-04, R-ERR-06).
- [ ] لا `catch`/`except` فارغ أو ابتلاع صامت؛ linter أخضر (§3).
- [ ] `healthcheck` مربوط لكل خدمة في `docker-compose.yml` (§4).
- [ ] سجلّ LiteLLM JSON بسطر واحد + `request_id` (litellm_call_id) + سطر الكلفة (§5)؛ الانتشار عبر الطبقات مؤجَّل (Phase 1، R-ERR-15/19).
- [ ] كل سطر `ERROR` قابل للتصرّف دون قراءة الكود (§6 / R-ERR-20).
