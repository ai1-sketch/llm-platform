# PROGRESS_MAP — خريطة التتبّع الحيّة (Resume Point)

> **R-PROG-00 (أعلى أولوية):** هذا **أوّل ملف يُقرأ عند الاستئناف**. حدّثه **بعد كل خطوة ذات قيمة** (التحديث جزء من الخطوة لا اختياري). سجّل **القرارات المعمارية فقط** في [DECISIONS](DECISIONS.md) كـ ADR — لا يلزم لمسه في كل تغيير. عند ضياع السياق، هذا الملف هو مصدر الحقيقة.
>
> الحالة: `[ ]` لم يبدأ · `[~]` جارٍ · `[x]` تمّ. كل بند `P-NN` منجَز يربط PR/قرار في [DECISIONS](DECISIONS.md). مرجع DoD في [CONSTITUTION](CONSTITUTION.md) §3.

> **آخر تحديث:** 2026-06-24 · **المحدِّث:** Tech Lead (state & continuity)

---

## 1. الحالة الآن (سطر واحد)
**P-01 شغّال end-to-end ✅.** المنصّة تعمل فعلياً: Open WebUI → LiteLLM → Gemma 4 (GPU) — كل الخدمات healthy، طلب تجريبي نجح عبر البوّابة، الواجهة على http://127.0.0.1:3000. التالي: تقوية (virtual key، تثبيت الوسوم، max_tokens لوضع تفكير Gemma) + تأكيد P-05.

## 2. أُنجِز مؤخّراً
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
- [x] **🎉 P-01 شغّال end-to-end (2026-06-24):** Docker Desktop + GPU passthrough (RTX 4050 داخل الحاوية) + 4 خدمات healthy + Gemma 4 محمّل على GPU (~2.4GB) + طلب نجح عبر البوّابة (`company-chat` → "2 + 2 equals 4"، مع reasoning). الواجهة على http://127.0.0.1:3000.

## 3. التالي مباشرةً (Next Up)
> أمسك بنداً واحداً، نفّذه، ثم حدّث القسمين 2 و 3 (والقسم 1).

1. [ ] **تقوية P-01:** استبدل master-key بـ virtual key للواجهة (`litellm /key/generate`)؛ ثبّت وسوم الصور (digests). [✓ تم ضبط max_tokens=2048 افتراضي في litellm-config — جواب كامل مؤكَّد.]
2. [ ] **تأكيد P-05:** تحقّق أن لوغ JSON يُصدر `request_id` + كلفة، وحقل `service=litellm` (R-ERR-16).
3. [ ] تنفيذ ما تبقّى من Phase 1 ثم التخطيط لـ Phase 2 (سحابة/vLLM عند الحاجة).

---

## 4. أهداف Phase 1 — البوّابة + الواجهة (1–10 مستخدمين)

| المعرّف | الهدف | الحالة |
|---|---|---|
| **P-00** | حسم أدوات الجودة وعتباتها وتوثيق المبرّر — [ADR-008](DECISIONS.md). (القرار محسوم؛ إنشاء ملفات الـ scaffolding هو بند "التالي مباشرةً".) | [x] |
| **P-01** | `compose/docker-compose.yml` يشغّل `open-webui` + `litellm` + `llamacpp` + `postgres` بـ `docker compose up`. | [x] **شغّال end-to-end** (4 خدمات healthy، GPU داخل الحاوية، طلب عبر البوّابة نجح، الواجهة على :3000) |
| **P-02** | `config/litellm/litellm-config.yaml`: موديل managed واحد خلف العقد `/v1`. | [ ] |
| **P-03** | `config/env/.env.example` يغطّي كل المفاتيح المطلوبة (لا قيم حقيقية). | [ ] |
| **P-04** | منفذ البوّابة غير مكشوف؛ الوصول داخل شبكة Docker فقط (R-ARCH-24). | [ ] |
| **P-05** | رصد بحدّ أدنى: كل مسار طلب يُصدر `request_id` + سجلّ كلفة (سياسة الرصد). | [ ] |

## 5. Phase 2+ — صناديق أكبر (محجوز، ليس الآن)

| المعرّف | الهدف | الحالة |
|---|---|---|
| **P-10** | self-host عبر `llama.cpp`/`vLLM` خلف نفس العقد — يفرضه طلب خصوصية/حجم حقيقي. | [ ] |

> لا يُضاف بند Phase 2+ قبل عبور حارس التضخيم ([CONSTITUTION](CONSTITUTION.md) §5) وتسجيل المبرّر في [DECISIONS](DECISIONS.md).

---

## 6. أسئلة / عوائق مفتوحة
> صيغة كل بند: `[OPEN] الوصف — مالكه — أثره`.

- [RESOLVED] **تعارض اسم خدمة LiteLLM:** وُحّد حقل `service` على `litellm` في `ERROR_AND_OBSERVABILITY_POLICY` ليطابق `R-ARCH-31` واسم خدمة Docker (يدعم تتبّع `request_id` عبر الطبقات R-ERR-25).
- [RESOLVED] الـ backend الابتدائي = **موديل Gemma 4 المحلي** (قرار المالك، [ADR-010](DECISIONS.md))؛ managed تبديل سطر واحد لاحقاً.
- [RESOLVED] تشغيل المحرّك = **Docker مع GPU** (قرار المالك، [ADR-011](DECISIONS.md)).
- [RESOLVED] صورة `ghcr.io/ggml-org/llama.cpp:server-cuda` **تدعم gemma4** (master يومي، الدعم منذ إبريل 2026) — لا حاجة لصورة مخصّصة. شرط: تعريف NVIDIA لويندوز يدعم WSL2 GPU + Docker Desktop WSL2.
- [OPEN] **تحقّق عند أوّل `docker compose up`:** GPU داخل الحاوية (`docker exec llamacpp nvidia-smi`)، تحميل الموديل بلا "unknown architecture"، وأداة healthcheck المتوفّرة. — SRE
- [OPEN] **R-ERR-16 (حقل `service=litellm` في سجل JSON):** لا يُعتمَد محقّقاً — يُتحقَّق فعلياً عند أوّل `docker compose up`؛ إن لم تُصدره الصورة يُؤجَّل لأوّل adapter. — SRE
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
| نقطة البدء | موديل **managed أولاً** | ADR-006 |
| نطاق المرحلة الأولى | **لا** Kubernetes / SSO / HA / autoscaling (YAGNI) | ADR-007 |

---

### كيفية التحديث (تذكير)
- بعد كل خطوة ذات قيمة: انقل البند من القسم 3 → 2، حدّث القسم 1 وتاريخ آخر تحديث.
- قرار **معماري** فقط؟ سجّله كـ ADR في [DECISIONS](DECISIONS.md) ثم أضف صفّاً في القسم 7 (التغييرات غير المعمارية لا تلمس DECISIONS).
- عائق جديد؟ أضفه في القسم 6 بصيغة `[OPEN]`؛ احذفه عند الحلّ.
