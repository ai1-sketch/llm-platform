# RUNBOOK — تشغيل المنصّة الحيّة (5 خدمات، OWUI أساسي، محرّك vLLM، قاعدتان مخصّصتان)

> دليل تشغيلي موجز للستاك الفعلي بعد [ADR-025](DECISIONS.md)/[ADR-028](DECISIONS.md)/[ADR-030](DECISIONS.md): `open-webui` + `litellm` + `vllm` (Qwen3 4B، GPU) + `postgres-litellm` + `postgres-openwebui`. مصدر الحقيقة للإعداد = [compose/docker-compose.yml](../compose/docker-compose.yml) · [config/litellm/litellm-config.yaml](../config/litellm/litellm-config.yaml) · [config/vllm/vllm-config.yaml](../config/vllm/vllm-config.yaml) · [config/env/.env.example](../config/env/.env.example). الحالة في [PROGRESS_MAP](PROGRESS_MAP.md).

## التشغيل
```bash
# شرط مسبق: تأكّد أن الـ GPU يمرّ للحاويات (وتعريف NVIDIA حديث — صورة vLLM تحتاج R580+ لـ CUDA 13)
docker run --rm --gpus all nvidia/cuda:13.0.2-base-ubuntu22.04 nvidia-smi
# الأسرار: انسخ القالب واملأه (openssl rand -hex 32)، وولّد OPENWEBUI_LITELLM_KEY (أدناه)
cp config/env/.env.example config/env/.env
# لا تنزيل موديل يدوي: vLLM يسحب الموديل (من vllm-config.yaml) تلقائياً من HuggingFace أوّل تشغيل إلى volume الكاش
docker compose --env-file config/env/.env -f compose/docker-compose.yml up -d
docker compose --env-file config/env/.env -f compose/docker-compose.yml ps   # 5 خدمات (vllm يحتاج دقائق أوّل مرة)
```
الواجهة: http://127.0.0.1:3000 — **على قاعدة نظيفة، أوّل حساب تنشئه عبر الواجهة يصير الأدمن** (bootstrap رغم `ENABLE_SIGNUP=false`).

## تهيئة قاعدتَي postgres — نسخة لكل تطبيق + least-privilege (ADR-029/030)
النموذج: **نسخة postgres مخصّصة لكل تطبيق** (`postgres-litellm`، `postgres-openwebui`)، وفي كل نسخة: superuser ‏`postgres` **للإدارة فقط** (لا يتصل به تطبيق) + دور تطبيق عادي يملك قاعدته + ‏`REVOKE CONNECT FROM PUBLIC`.
- على **volume نظيف**: سكربت init الخاص بكل نسخة (`config/postgres/{litellm,openwebui}-init/10-app-role.sh`) يبني كل ذلك **تلقائياً** (مُثبَت حيّاً).
- على **volume قائم** (init لا يعمل تلقائياً): نفّذ سكربت النسخة يدوياً — idempotent وكلمات السرّ من بيئة الحاوية:
```bash
docker exec llm-platform-postgres-litellm-1   bash /docker-entrypoint-initdb.d/10-app-role.sh
docker exec llm-platform-postgres-openwebui-1 bash /docker-entrypoint-initdb.d/10-app-role.sh
```
**للانتقال لـ Postgres خارجي/مُدار لاحقاً (ADR-029/030):** كل نسخة تُرفَع لمكانها المُدار باستقلال — غيّر `host` في رابط (روابط) التطبيق المعنيّ في compose (غالباً مع `?sslmode=require`) — تغيير رابط فقط، بلا تغيير schema. للترحيل: `pg_dump` قاعدة النسخة ثم استعادة على المُدارة.

> ⏱️ **الإقلاع البارد لـ vLLM:** أوّل تشغيل = تنزيل الموديل (~2.5GB) + torch.compile (دقائق). الإقلاعات التالية أسرع بكثير (كاش `vllm-cache`). healthcheck يصبر (`start_period: 600s`) — راقب `logs vllm` لا تستعجل.

## توليد/تجديد مفتاح OWUI الافتراضي (virtual key)
litellm غير مكشوف خارجياً (R-ARCH-24)، فالأمر يُنفَّذ **داخل حاوية litellm** (المفتاح الرئيسي متاح فيها كمتغيّر بيئة — لا تستخدم master مباشرةً للواجهة):
```bash
docker exec llm-platform-litellm-1 python -c "
import os, httpx
r = httpx.post('http://localhost:4000/key/generate',
  headers={'Authorization': 'Bearer ' + os.environ['LITELLM_MASTER_KEY']},
  json={'key_alias': 'open-webui'}, timeout=30)
print(r.json()['key'])"
# ضع الناتج في OPENWEBUI_LITELLM_KEY بـ config/env/.env ثم:
# docker compose --env-file config/env/.env -f compose/docker-compose.yml up -d open-webui
```

## أعطال شائعة → الحل
| العَرَض | السبب/الحل |
|---|---|
| لا GPU في الحاوية | فحص `nvidia-smi` أعلاه؛ Docker Desktop خلفية WSL2 + تعريف NVIDIA يدعم WSL2 |
| `vllm` يفشل بـ CUDA error عند الإقلاع | تعريف NVIDIA أقدم من R580 (الصورة CUDA 13) — حدّث التعريف أو ثبّت digest نسخة `-cu129` |
| `vllm` يفشل: `UVA is not available` | ‏WSL2 لا يدعم UVA التي يتطلّبها Model Runner V2 — تأكّد `VLLM_USE_V2_MODEL_RUNNER=0` (افتراضي compose؛ اضبط 1 على Linux أصلي/سحابة) |
| `vllm` يفشل: `Free memory ... less than GPU memory utilization` | VRAM مشغولة (شاشة/تطبيقات) — أغلق تطبيقات GPU أو اخفض `gpu-memory-utilization` في [vllm-config](../config/vllm/vllm-config.yaml) |
| `vllm` يفشل: `max seq len is larger than ... KV cache` | اخفض `max-model-len` أو ارفع `gpu-memory-utilization` (نفس الملف) |
| طلب يفشل 400 "maximum context length" | vLLM يرفض بدل القصّ عند prompt+max_tokens > النافذة — قصّر المحادثة أو اخفض `max_tokens` في الطلب (لا نضبط افتراضياً — ADR-028) |
| تنزيل الموديل يفشل 401/403 | موديل مقفل (gated) على HF — اقبل الترخيص على huggingface.co وضع `HF_TOKEN` في `.env` (غير مطلوب لـ Qwen3-4B-AWQ) |
| `litellm` unhealthy | مفاتيح `.env` (master/salt)؛ صحّة `litellm-config.yaml`؛ `logs litellm` |
| OWUI لا يقلع / خطأ اتصال قاعدة | تأكّد قاعدة/دور `openwebui` موجودان (قسم التهيئة أعلاه) و`OPENWEBUI_DB_PASSWORD` مضبوط؛ `logs open-webui` |
| الدردشة 5xx | راجع `ps` + `logs` للخدمة المعنيّة؛ تتبّع `request_id` عبر الطبقات (R-ERR-19) |
| رفع صورة في الدردشة → خطأ/تجاهل | متوقَّع: الرؤية معلّقة مؤقتاً (موديل الاختبار نصّي — [ADR-028](DECISIONS.md))؛ تعود بتبديل الموديل مع GPU أكبر |
| ذاكرة/RAG لا تسترجع في OWUI | `ENABLE_MEMORIES=true`؛ أوّل استخدام RAG يُنزّل موديل التضمين المحلّي؛ راجع أدناه |

## تدفّق البيانات في OWUI (RAG + Memory)
- **ملفات (RAG):** رفع → OWUI يستخرج النص → تقطيع (1000/100) → تضمين **all-MiniLM-L6-v2 (384) محلّياً داخل OWUI** → **pgvector** (قاعدة `openwebui` — [ADR-029](DECISIONS.md)، كان Chroma) → استرجاع top-k (3) → حقن المقاطع + استشهادات في الدردشة.
- **حقائق (Memory):** `Settings > Personalization > Memory` → مجموعة per-user `user-memory-{id}` (بحث دلالي) → حقن كـ"User Context:".
- **⚠️ استثناء حوكمي ([ADR-025](DECISIONS.md)):** تضمين OWUI **محلّي خارج البوّابة** (ليس عبر LiteLLM) — انحراف موثّق ومقصود عن قاعدة "كل مرور موديل عبر البوّابة" (R-ARCH-10)، قابل للعكس بالإعداد.
- **ℹ️ الرؤية (الصور) معلّقة مؤقتاً ([ADR-028](DECISIONS.md)):** لا موديل multimodal يتّسع على 6GB تحت vLLM — تعود مع GPU أكبر بتبديل الموديل (بلا mmproj؛ برج الرؤية داخل checkpoint HF). وسوم `<think>` من Qwen3 تصل inline وOWUI يطويها (لا `--reasoning-parser` — علّة عرض مفتوحة open-webui#24697).

## نسخ احتياطي واستعادة (طبقة البيانات — حيث كل القيمة)
بعد [ADR-029](DECISIONS.md)/[ADR-030](DECISIONS.md): **بيانات OWUI (ميتاداتا + متجهات) في نسخته `postgres-openwebui`**، وحالة البوّابة في `postgres-litellm` — لا SQLite/Chroma. النسخة الأساسية = **`pg_dump` لكل نسخة** (بحساب إدارتها). يبقى `openwebui-data` يحوي **ملفّات الرفع (blobs)** فقط. **فقدان `LITELLM_SALT_KEY` غير قابل للاستعادة** (R-ARCH-44) — احفظ `.env` بأمان خارج git. *(`hf-cache`/`vllm-cache` قابلان لإعادة الإنشاء.)*
```bash
mkdir -p backups
# كل قاعدة من نسختها (منطقيّاً، بلا إيقاف) — بحساب إدارة النسخة (ADR-029/030)
docker exec llm-platform-postgres-litellm-1   pg_dump -U postgres -d litellm   | gzip > backups/litellm-$(date +%F).sql.gz
docker exec llm-platform-postgres-openwebui-1 pg_dump -U postgres -d openwebui | gzip > backups/openwebui-$(date +%F).sql.gz
# ملفّات الرفع (blobs على الـ volume)
docker run --rm -v llm-platform_openwebui-data:/d -v "$PWD/backups":/b alpine \
  tar czf /b/owui-uploads-$(date +%F).tgz -C /d uploads
# استعادة قاعدة: zcat backups/openwebui-<تاريخ>.sql.gz | docker exec -i llm-platform-postgres-openwebui-1 psql -U postgres -d openwebui
```

## اختبار دخان (smoke) يدوي — مسار الدردشة + request_id
CI لا يشغّل الموديل (يحتاج GPU)، فالتحقّق end-to-end يدوي عبر هذا السكربت:
```bash
KEY=$(grep '^OPENWEBUI_LITELLM_KEY=' config/env/.env | cut -d= -f2-)
docker exec -e K="$KEY" llm-platform-litellm-1 python -c "
import os, httpx
r = httpx.post('http://localhost:4000/v1/chat/completions',
  headers={'Authorization': 'Bearer ' + os.environ['K']},
  json={'model':'Qwen3 4B','stream':False,'max_tokens':64,
        'messages':[{'role':'user','content':'قل: تمام'}]}, timeout=300)
print('status', r.status_code, r.json()['choices'][0]['message']['content'][:80])
"   # 200 + ردّ = المسار حيّ. تتبّع request_id: يظهر litellm_call_id في سجلّات litellm عند LITELLM_LOG=DEBUG (وسطر الكلفة يظهر على INFO: "Spend tracking").
```
*(الثوابت المعمارية الساكنة — أسماء الخدمات/الكشف/الربط — مفروضة آلياً في CI عبر `.github/scripts/check_invariants.py`، ADR-026.)*

## تبديل الموديل / ترقية GPU / التحوّل لـ managed
- **موديل محلي آخر:** عدّل `model` + `served-model-name` في [config/vllm/vllm-config.yaml](../config/vllm/vllm-config.yaml) (+ حدّث `model` المطابق و`model_name` المعروض في [litellm-config](../config/litellm/litellm-config.yaml) — ADR-017) ثم `up -d`. التنزيل تلقائي (موديل مقفل؟ `HF_TOKEN` في `.env`).
- **ترقية GPU:** ارفع `gpu-memory-utilization` (حتى ~0.9) و`max-model-len` في نفس الملف — **لا شيء آخر يتغيّر** (ADR-028).
- **managed (مثلاً Gemini):** سطر واحد في [litellm-config](../config/litellm/litellm-config.yaml) (model/api_key) — R-ARCH-45 / [ADR-023](DECISIONS.md). البقية بلا تغيير.
