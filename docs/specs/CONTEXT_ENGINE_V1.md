# Context Engine — مواصفة وخطة التنفيذ v1 (Living Spec)

> **الحالة:** ✅ معتمد ([ADR-019](../DECISIONS.md) + [ADR-020](../DECISIONS.md) مقبولان) — التنفيذ بدأ عند **M0**. · **آخر تحديث:** 2026-06-25 · **المسار المعتمد:** (أ) بناء معماري على Gemma المحلي.
>
> هذا الملف هو **المرجع الحيّ** لبناء Context Engine: الآلية، المتطلّبات، وكيف نعمل خطوة-خطوة حتى لا نضيع. يُحدَّث بعد كل خطوة. مرجع القرار في [DECISIONS](../DECISIONS.md)، ونقطة الاستئناف العامة في [PROGRESS_MAP](../PROGRESS_MAP.md)، و**الأساس والمبرّرات** (مقارنة الأطر + المراجعة العدائية) في [research/CONTEXT_ENGINE_RATIONALE](../../research/CONTEXT_ENGINE_RATIONALE.md).
>
> **ملاحظة حوكمة:** `docs/specs/` يحوي مواصفات هندسية تفصيلية حيّة، **معفاة من حدّ 180 سطر** (R-ARCH-05) الخاص بوثائق الحوكمة الأساسية — مُسجَّل في ADR-019.

---

## 0. الفهرس
1. [الهدف والنطاق](#1-الهدف-والنطاق)
2. [المبادئ الحاكمة](#2-المبادئ-الحاكمة)
3. [المعمارية — الصورة الكاملة](#3-المعمارية)
4. [القرارات المقفلة](#4-القرارات-المقفلة)
5. [نموذج البيانات + عقد MemoryItem](#5-نموذج-البيانات)
6. [خط الأنابيب: Retrieve → Normalize → Rank → Compose](#6-خط-الأنابيب)
7. [الـ Orchestrator: الواجهة ومسار الكتابة](#7-الorchestrator)
8. [التضمين والعربية](#8-التضمين-والعربية)
9. [الأمان والخصوصية (v1)](#9-الأمان)
10. [الإعدادات (Config)](#10-الإعدادات)
11. [المتطلّبات المسبقة (Prerequisites)](#11-المتطلبات-المسبقة)
12. [خطة البناء المرحلية (M0→M5)](#12-خطة-البناء)
13. [الاختبار و Eval](#13-الاختبار)
14. [المؤجَّل لـ v2 (صريح)](#14-المؤجل)
15. [المخاطر والأسئلة المفتوحة](#15-المخاطر)
16. [نقطة الاستئناف (Resume)](#16-نقطة-الاستئناف)

---

<a id="1-الهدف-والنطاق"></a>
## 1. الهدف والنطاق

**الهدف:** طبقة "Context Engine" خلف بوّابة LiteLLM (نقطة دخول وحيدة = Memory Orchestrator) تبني **أفضل سياق ممكن** لكل طلب من ذاكرات متعدّدة، بحيث **حجم الذاكرة المخزَّنة مستقل عن نافذة الموديل**.

**v1 يشمل:** ذاكرة مستخدم دلالية · التقاط محادثة حرفي + استرجاع · استرجاع ملفات أساسي · عدّ توكنات محافظ (بايتات، [ADR-021](../DECISIONS.md)) · فحص ميزانية صارم · عقد `MemoryItem` موحّد · خط الأنابيب الكامل (Retrieve/Normalize/Rank/Compose) · Orchestrator + ingest موحّد.

**v1 لا يشمل (مؤجَّل v2):** التلخيص بـ LLM · سياسة High/Low-Water · RLS الكامل + virtual keys per-user · parent/child file chunks · Reflection memory · LLM router · طابور كتابة دائم.

**واقع مهم:** نافذة Gemma الحالية = 4096 → ميزانية الحقن الفعلية صغيرة (مئات–~1500 توكن). المعمارية صحيحة ومستقبلية؛ الفائدة الكاملة تظهر مع موديل أكبر (نفس الكود).

<a id="2-المبادئ-الحاكمة"></a>
## 2. المبادئ الحاكمة
- **المسار الحارّ (القراءة) خالٍ من LLM** — حتمي بالكامل. أي توليد (تلخيص/استخراج) = مجدول/غير متزامن خارج الـ GPU الحيّ.
- **إعادة استخدام Postgres** (+pgvector)، لا قاعدة جديدة. كل شيء **وحدات داخل خدمة `memory`**، لا حاوية جديدة (عدا حاوية embeddings الصغيرة).
- **قابلية التبديل:** كل مرحلة/مخزن خلف عقد ضيّق. `MemoryItem` مصدر-محايد (يفتح الباب لـ Reflection ومصادر مستقبلية بلا إعادة تصميم).
- **anti-bloat / YAGNI:** ابدأ نحيفاً، قِس، ثم وسّع. كل رقم في الإعدادات، **لا رقم مرتبط بالموديل**.
- **الخطأ يُعلِن عن نفسه:** JSON + request_id عبر الطبقات. fail-open للذاكرة (لا تكسر المحادثة).

<a id="3-المعمارية"></a>
## 3. المعمارية — الصورة الكاملة
```
سؤال المستخدم
   │  (LiteLLM pre-call hook — المُحوّل الوحيد للمنصّة)
   ▼
Memory Orchestrator  ── جامع (assemble) + كاتب (ingest موحّد)
   │ يجمع أدلّة من المخازن ببوّابات رخيصة + استرجاع بالصلة (بلا LLM، بلا تصنيف-نيّة)
   ├── User Memory (per-user)        ┐
   ├── Conversation Memory (per-conv)├─ كلها تُطبَّع إلى MemoryItem
   └── File Memory (per-file)        ┘   [+ Reflection ← v2، نفس العقد]
   ▼
Context Builder (خط أنابيب حتمي v1):
   Retrieve → Normalize(→MemoryItem) → Rank(Rel+Rec+Imp+Conf) → Compose(dedup+order+budget)
   ▼
كتلة سياق واحدة ضمن نافذة الموديل الحالي  →  Gemma (أو أي موديل)

مبدأ مفصلي: حجم الذاكرة (قد يكون ضخماً) ≠ حجم المحقون (يلائم النافذة لكل طلب).
```

<a id="4-القرارات-المقفلة"></a>
## 4. القرارات المقفلة
1. **3 جداول لكل-مصدر** (نطوّر `memory.user_memory` مكانه؛ conversation + file جداول خاصة). `Normalize` = مُحوِّل `normalize(native_row)->MemoryItem`؛ المراحل التالية لا ترى شكل المخزن.
2. **عقد واحد = `MemoryItem`** (Pydantic). يحمل `embedding_ref` (وصف) **لا متجهات خام**؛ متجهات الـ dedup عبر **قناة جانبية** `dict[item_id→vector]` من Retrieve؛ `provenance` كائن مُهيكَل (Rank يقرأ `provenance.origin`).
3. **مفردات موحّدة:** مفتاح العزل `user_id` · PK `bigserial` + `item_id uuidv7` · `status` enum `{active|archived|superseded|deleted}` · `content`↔`text` يُوحَّد مرّة في Normalize.
4. **تبديل صورة pgvector = خطوة صفر** (ADR-020 يعدّل P-01؛ digest جديد + checkpoint قبل/بعد).
5. **تثبيت بُعد التضمين** بقياس الموديل **قبل أي `ALTER TABLE`**؛ البُعد **مُصدَّر بالإصدار** (تغييره = عمود v2 + backfill).
6. **النافذة من الإعداد (صحّحه [ADR-021](../DECISIONS.md)):** الميزانية = `min(CTX_INJECTION_BUDGET, CTX_MODEL_WINDOW − CTX_RESERVED_TOKENS)` (config-driven، بلا قراءة `model_info`، **fail-open** لا fail-fast)؛ **عدّ توكنات = بايتات UTF-8** (محافظ مُثبَت `≥` عدّ الموديل، باختبار خاصية على عيّنات أرقام/IBAN مقيسة) لا tokenizer دقيق؛ تأكيد صارم `injected ≤ budget` نقطة واحدة في Compose (bytes ≥ real ⇒ real ≤ budget). (tokenizer دقيق + قراءة model_info + fail-fast = مؤجَّلة v2.)
7. **`normalize_ar` واحدة** مُصدَّرة بالإصدار (فهرسة = استعلام، بايت-بايت)؛ تملكها وحدة التضمين، يستوردها Retrieve والكتابة.
8. **seam كتابة واحد** = `ingest` موحّد؛ كتابة inline-async (بلا طابور/worker في v1)؛ `POST /v1/memories` يبقى shim لحقائق المستخدم (لا تنكسر الـ17 اختباراً).

<a id="5-نموذج-البيانات"></a>
## 5. نموذج البيانات + عقد MemoryItem

**`MemoryItem` (Pydantic — العقد داخل العملية):**
| الحقل | النوع | من يضبطه |
|---|---|---|
| `id` | bigserial (DB PK) | DB |
| `item_id` | UUIDv7 | الكتابة (مرتّب زمنياً) |
| `source_type` | enum `user_fact\|conversation_chunk\|document_chunk\|reflection*` | الكتابة (*محجوز v1) |
| `scope` | `{user_id*, conversation_id?, file_id?, chunk_no?}` | الكتابة (`user_id` إلزامي = مفتاح العزل) |
| `text` | text | Normalize |
| `embedding_ref` | `{model_version, dim, present}` | الكتابة (وصف فقط) |
| `provenance` | `{origin, writer, source_ref, ingested_at, content_hash}` | الكتابة (anti-poisoning/GDPR/dedup) |
| `confidence` | real [0,1]=1.0 | الكتابة (user=1.0، reflection v2<1) |
| `importance` | real [0,1]=0.5 | الكتابة/heuristic (fact=0.8, summary=0.6, chunk=0.4) |
| `created_at/updated_at/last_accessed` | timestamptz | DB / async |
| `token_estimate` | int | الكتابة (tokenizer) — الميزانية تقرأه فقط |
| `status` | enum | السياسة/GDPR |
| `metadata` | jsonb | حسب المصدر |

**الجداول (3):** `memory.user_memory` (مُطوَّر مكانه)، `memory.conversation_memory`، `memory.file_memory`. كل جدول: الأعمدة المشتركة أعلاه + `embedding halfvec(<dim>)` + فهرس **HNSW** على المتجه + عمود `tsvector` + فهرس **GIN** للنص + فهرس على `user_id`. فهارس HNSW جزئية `WHERE status != 'deleted'`.

<a id="6-خط-الأنابيب"></a>
## 6. خط الأنابيب: Retrieve → Normalize → Rank → Compose

- **Retrieve:** بوّابات رخيصة حتمية (هل للمستخدم ملفات؟ محادثة طويلة؟ ملف رُفع؟) → استعلام المخازن المرشّحة **بالتوازي**؛ لكل مخزن **هجين**: dense (pgvector/HNSW على halfvec) + lexical (tsvector) مدموجان بـ **RRF (k=60)**؛ تطبيق `relevance_threshold` و `retrieval_top_k`. يُصدِر `relevance_raw` موحّد + قناة المتجهات الجانبية. بلا LLM.
- **Normalize:** `normalize(native_row)->MemoryItem` لكل مخزن؛ توحيد `content↔text` و`status` والـ provenance هنا. بعد هذه المرحلة لا أحد يعرف مصدر الصفّ.
- **Rank:** `Score = w_rel·Rel + w_rec·Rec + w_imp·Imp + w_conf·Conf`؛ `Rel` min-max **لكل طلب** عبر المجموعة المدموجة؛ `Rec` تحلّل بنصف-عمر؛ `Imp/Conf` من الأعمدة (لا LLM). أوزان **لكل نوع** (ملفات: Rel غالب؛ محادثة: +Rec؛ حقائق: currency).
- **Compose (+ Budget Manager):** النافذة من الإعداد (`CTX_MODEL_WINDOW`، [ADR-021](../DECISIONS.md)) → `budget = min(CTX_INJECTION_BUDGET, window − CTX_RESERVED_TOKENS)` → تخصيص بحصص قابلة للضبط ثم ملء بالترتيب → **dedup** بالتشابه (≥0.88 عبر القناة الجانبية، أو `content_hash`) → اختيار تمثيل (كامل/مقاطع) بالحجم → ترتيب U-shaped (تخفيف lost-in-the-middle) → كتلة محصورة (سياج "بيانات لا تعليمات" ضد الحقن) → **تأكيد `injected+reserved ≤ window`**.

<a id="7-الorchestrator"></a>
## 7. الـ Orchestrator: الواجهة ومسار الكتابة
- **`assemble_context(user_id, conversation_id, query, model) -> context_block`** (قراءة، بلا LLM) — يناديه الـ hook في `async_pre_call_hook`.
- **`ingest(...)`** (كتابة موحّدة، مُوجَّهة بـ `source_type`): حقيقة مستخدم (HITL، بادئة "تذكّر:") · دور محادثة (التقاط حرفي) · ملف (هضم). التضمين inline-async؛ بلا طابور دائم v1.
- **الـ hook يبقى المُحوّل الوحيد** (نحيف): يقرأ الهوية، ينادي assemble، يسجّل/يصفّ ingest عند النجاح. fail-open + JSON + request_id (سياسة R-ERR).

<a id="8-التضمين-والعربية"></a>
## 8. التضمين والعربية
- **حاوية `embeddings` صغيرة** (Qwen3-Embedding-0.6B-GGUF، CPU، behind `/v1/embeddings` عبر البوّابة) — لا تزاحم Gemma على الـ GPU.
- `halfvec(<dim مُثبَّت>)`؛ بادئة Instruct/Query على الاستعلام فقط.
- **`normalize_ar` واحدة** (همزة/تشكيل/tatweel) مُصدَّرة بالإصدار، مستخدمة وقت الفهرسة والاستعلام (تماثل = شرط الدقّة).

<a id="9-الأمان"></a>
## 9. الأمان والخصوصية (v1)
- العزل: `WHERE user_id=$1` في كل استعلام + **بوّابة داخلية** (الحدّ الأمني الحالي، ADR-012).
- `provenance` على كل عنصر + **حذف-للنسيان** (per-user / per-item / per-file، حذف فعلي).
- **اختبار عزل على Postgres حقيقي** (لا mock): u1 لا يرى u2 — بوّابة CI.
- **v2 إلزامية قبل أي فتح خارجي:** RLS كامل (role split + FORCE + WITH CHECK + GUC) + virtual keys per-user + تجريد الهوية من الـ header. مُسجَّل صراحةً.

<a id="10-الإعدادات"></a>
## 10. الإعدادات (Config — كلها قابلة للتعديل، لا رقم مرتبط بالموديل)
`recent_verbatim_turns` · `retrieval_top_k` · `relevance_threshold` · `model_reserved_tokens` · `injection_budget_policy` (حصص لكل نوع) · `score_weights` (لكل نوع) · `dedup_threshold` · `embedding_model_version` + `embedding_dim` · `routing_gates`. (v2: `archive_high_water` · `archive_low_water` · `summary_chunk_size`.)

<a id="11-المتطلبات-المسبقة"></a>
## 11. المتطلّبات المسبقة (تُنجَز قبل أي جدول/متجه)
> ✅ **كلها مُنجَزة (M0)** — التفاصيل في §16. (pgvector مُفعّل · البُعد=1024 · conversation_id=`X-OpenWebUI-Chat-Id`.)
- **P-req-1:** تبديل صورة Postgres إلى `pgvector/pgvector:pg16` + إعادة تثبيت digest + checkpoint (ADR-020). bootstrap `CREATE EXTENSION IF NOT EXISTS vector/pg_trgm/unaccent` يفشل **بصوت** (CONFIG error) لا stack-trace.
- **P-req-2:** قياس بُعد Qwen3-Embedding-0.6B (تضمين نصّ، قياس الطول) → تثبيت `embedding_dim` في مكان واحد.
- **P-req-3:** spike لـ `conversation_id`: تأكيد كيف يمرّره Open WebUI (header/حقل) وثباته عبر التعديل/إعادة التوليد — قبل بناء التقاط الأدوار/scoping الملفات.

<a id="12-خطة-البناء"></a>
## 12. خطة البناء المرحلية (M0→M5) — "كيف نعمل حتى لا نضيع"
> كل مرحلة: نطاق محدّد + معيار "تمّ" (DoD §3) + checkpoint. لا ننتقل قبل خضرة البوّابة.

- **M0 — المتطلّبات المسبقة:** P-req-1/2/3 أعلاه. **DoD:** الـ stack يُقلع بصورة pgvector، الامتداد مُفعّل، البُعد مُثبَّت، conversation_id مؤكَّد. checkpoint.
- **M1 — البيانات + العقد:** هجرة `user_memory` مكانه (أعمدة المغلّف + halfvec) + جدولا conversation/file + فهارس (HNSW/GIN/tsvector) + `MemoryItem` Pydantic + مُحوّلات Normalize. **DoD:** bootstrap idempotent، round-trip للعنصر، اختبارات.
- **M2 — التضمين + Retrieve:** التضمين عند الكتابة + استرجاع هجين لكل مخزن + `normalize_ar` مشتركة + البوّابات الرخيصة. **DoD:** استرجاع مُرتّب لكل مخزن، تماثل عربي، اختبارات.
- **M3 — Rank + Compose + Budget:** محرّك الدرجات + عدّ توكنات محافظ (بايتات، [ADR-021](../DECISIONS.md)) + نافذة من الإعداد (fail-open) + تخصيص + dedup + ترتيب + **تأكيد عدم تجاوز النافذة** (ثابت CI). **DoD:** الميزانية لا تُتجاوز أبداً، حتمي، اختبارات.
- **M4 — Orchestrator + hook:** `assemble_context` + `ingest` موحّد + ربط الـ hook (قراءة/كتابة inline-async) + توجيه + fail-open + JSON/request_id + HITL. **DoD:** end-to-end عبر OWUI، اختبار عزل Postgres حقيقي، بوّابة خضراء.
- **M5 — ملفات (أساسي) + Eval:** هضم ملفات (تقطيع مسطّح) بعد تأكيد مسار الرفع + golden-set + قياس الجودة. **DoD:** سؤال عن ملف يسترجع المقطع الصحيح، الـ eval يعمل.

<a id="13-الاختبار"></a>
## 13. الاختبار و Eval
- **وحدات:** Normalize، Rank (درجات حتمية)، Compose (لا تجاوز نافذة — ثابت صارم)، dedup، normalize_ar (تماثل).
- **تكامل (Postgres حقيقي):** عزل per-user، استرجاع هجين، round-trip.
- **Eval harness:** مجموعة ذهبية (سؤال → المصدر/الجواب المتوقَّع) لقياس routing/retrieval/ranking قبل/بعد كل تغيير. **القياس قبل التوسّع.**
- بوّابة CI: `injected+reserved ≤ window` = ثابت أحمر عند الكسر.

<a id="14-المؤجل"></a>
## 14. المؤجَّل لـ v2 (صريح، خلف نفس العقود)
التلخيص بـ LLM + High/Low-Water · RAPTOR/هرمي · parent/child + Excel-row + إصدارات الملفات · RLS كامل + virtual keys per-user + تجريد header · Reflection memory · LLM router · ضغط/دمج بـ LLM · طابور كتابة دائم · config framework متقدّم.

<a id="15-المخاطر"></a>
## 15. المخاطر والأسئلة المفتوحة
- **نافذة 4096 ضيّقة:** الفائدة محدودة حتى موديل أكبر — مقبول (معماري أولاً).
- جودة العربية في التضمين/التطبيع → eval مبكر.
- تماثل `normalize_ar` فهرسة/استعلام = شرط دقّة (اختبار صارم).
- مسار رفع الملفات في OWUI غير مؤكَّد بعد (P-req-3 المرافق).
- تثبيت البُعد قرار شبه أحادي الاتجاه → نقيس قبل أي DDL.

<a id="16-نقطة-الاستئناف"></a>
## 16. نقطة الاستئناف (Resume)
**الحالة الآن:** معتمد، **M0 (المتطلّبات المسبقة) مكتمل ✅** — جاهزون لـ **M1**.
- ✅ **M0.1 (pgvector)** — صورة `pgvector/pgvector:pg16` (digest مثبّت)؛ البيانات سليمة (74 جدول litellm)؛ الامتدادات مُفعّلة (`vector 0.8.3`, `pg_trgm 1.6`, `unaccent 1.1`)؛ نسخة أمان `C:\tmp\litellm_backup.sql`. checkpoints v10/v11.
- ✅ **M0.4 (embeddings)** — خدمة `embeddings` (llama.cpp CPU، Qwen3-Embedding-0.6B-Q8_0، `--embedding --pooling last`، digest مثبّت) خلف `/v1/embeddings` عبر litellm (موديل `embed-default`). نداء تضمين نجح عبر البوّابة.
- ✅ **M0.2 (البُعد)** — مقيس فعلياً = **1024** (يؤكّد `halfvec(1024)`). `embedding_model_version = "qwen3-emb-0.6b-q8@1024"`، `embedding_dim = 1024` (مُصدَّر؛ تغييره = عمود v2 + backfill).
- ✅ **M0.3 (conversation_id)** — **`X-OpenWebUI-Chat-Id`** يحمل معرّف المحادثة، و**`X-OpenWebUI-Message-Id`** للـ provenance؛ يُمرَّران عبر `ENABLE_FORWARD_USER_INFO_HEADERS` المُفعّل. الثبات per-conversation مؤكَّد من المصدر؛ تحقّق التعديل/إعادة-التوليد عند بناء التقاط الأدوار (M4).
- ✅ **M1 (البيانات + العقد)** — 3 جداول (`user/conversation/file_memory`، عقد أعمدة موحّد من `schema.py`، `halfvec(1024)` + فهارس HNSW/GIN/item_id) · عقد `MemoryItem` (`models.py`) + مرحلة `Normalize` (`normalize.py`) · هجرة `user_memory` في-المكان **غير كاسرة** (L1 round-trip حيّ يعمل). البوّابة خضراء (ruff/mypy+pydantic-plugin/**26 pytest**). checkpoint v13.
- ✅ **M2a (الكتابة)** — `normalize_ar` (ar-v1، مشتركة فهرسة=استعلام) + عميل التضمين (`embeddings.py`) + **التضمين عند الكتابة** (fail-soft): الحقيقة تُخزَّن مع `embedding halfvec(1024)` + `content_tsv` + `content_hash` + `embedding_model_version`. مُتحقَّق حيّاً (`embedded:true`). البوّابة خضراء (34 pytest). checkpoint v14.
- ✅ **M2b (القراءة)** — `retrieve.py`: Retrieve الهجين (dense pgvector `<=>` + lexical tsvector → دمج **RRF** عبر المخازن) + نقطة `/v1/retrieve` + fail-soft (لفظي بلا تضمين). **مُتحقَّق حيّاً:** سؤال "ما وظيفتي؟" تصدّره فعلاً حقيقة "مهندس برمجيات" **بلا تطابق كلمات** (تطابق دلالي). 38 pytest. checkpoint v15.
- ✅ **M3 (Rank + Compose + Budget)** — `rank.py` (درجة حتمية Rel+Rec+Imp+Conf، min-max للصلة، اضمحلال حداثة) + `compose.py` (Context Builder: dedup بـ content_hash + **عدّ توكنات محافظ** + **ميزانية لا تتجاوز أبداً** + كتلة مُسيَّجة "بيانات لا تعليمات") + نقطة `/v1/assemble` (المسار الكامل). **مُتحقَّق حيّاً:** سؤال المهنة → كتلة (76 توكن ≤ 200) تتصدّرها 'مهندس برمجيات'. 49 pytest. checkpoint v16.
- ✅ **M4a (الربط بالدردشة)** — الـ LiteLLM hook يحقن السياق عبر `/v1/assemble` (دلالي/مُرتَّب/مُوازَن بدل جلب-الكل) بميزانية `CTX_INJECTION_BUDGET` قابلة للضبط؛ fail-open + request_id محفوظان. **مُتحقَّق حيّاً:** خُزِّن سرّ ('سنكري-إكس') في طلب، فاسترجعه Gemma في طلب **منفصل** — الذاكرة **مرئية في الدردشة الفعلية**. 49 pytest. checkpoint v17.
- **التالي: M4b** — التقاط أدوار المحادثة في `conversation_memory` (عبر `x-openwebui-chat-id`) → ثم **M5** (ملفات + eval harness).
