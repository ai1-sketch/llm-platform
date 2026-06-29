# RUNBOOK — تشغيل المنصّة الحيّة (4 خدمات، OWUI أساسي)

> دليل تشغيلي موجز للستاك الفعلي بعد [ADR-025](DECISIONS.md): `open-webui` + `litellm` + `llamacpp` (Gemma 4، GPU) + `postgres`. مصدر الحقيقة للإعداد = [compose/docker-compose.yml](../compose/docker-compose.yml) · [config/litellm/litellm-config.yaml](../config/litellm/litellm-config.yaml) · [config/env/.env.example](../config/env/.env.example). الحالة في [PROGRESS_MAP](PROGRESS_MAP.md).

## التشغيل
```bash
# شرط مسبق: تأكّد أن الـ GPU يمرّ للحاويات
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
# الأسرار: انسخ القالب واملأه (openssl rand -hex 32)، وولّد OPENWEBUI_LITELLM_KEY (أدناه)
cp config/env/.env.example config/env/.env
# الموديل: ضع GGUF في models-gemma4/ (gemma-4-E2B-it-qat-*.gguf + mmproj-F16.gguf)
docker compose --env-file config/env/.env -f compose/docker-compose.yml up -d
docker compose --env-file config/env/.env -f compose/docker-compose.yml ps   # 4 خدمات healthy
```
الواجهة: http://127.0.0.1:3000

## توليد/تجديد مفتاح OWUI الافتراضي (virtual key)
```bash
# عبر litellm (master key من .env) — لا تستخدم master مباشرةً للواجهة (R-ARCH)
curl -s http://localhost:4000/key/generate -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H 'Content-Type: application/json' -d '{"key_alias":"open-webui"}'
# ضع الـ key الناتج في OPENWEBUI_LITELLM_KEY بـ .env ثم أعد تشغيل open-webui
```
*(litellm غير مكشوف خارجياً؛ نفّذ هذا من داخل الحاوية أو على شبكة compose.)*

## أعطال شائعة → الحل
| العَرَض | السبب/الحل |
|---|---|
| لا GPU في الحاوية | فحص `nvidia-smi` أعلاه؛ Docker Desktop خلفية WSL2 + تعريف NVIDIA يدعم WSL2 |
| `llamacpp` لا يُحمِّل الموديل | تأكّد `MODEL_DIR`/`MODEL_FILE` ووجود GGUF؛ راجع `docker compose logs llamacpp`؛ VRAM ~3GB/6 |
| `litellm` unhealthy | مفاتيح `.env` (master/salt)؛ صحّة `litellm-config.yaml`؛ `logs litellm` |
| الدردشة 5xx | راجع `ps` + `logs` للخدمة المعنيّة؛ تتبّع `request_id` عبر الطبقات (R-ERR-19) |
| ذاكرة/RAG لا تسترجع في OWUI | `ENABLE_MEMORIES=true`؛ أوّل استخدام RAG يُنزّل موديل التضمين المحلّي؛ راجع أدناه |

## تدفّق البيانات في OWUI (RAG + Memory)
- **ملفات (RAG):** رفع → OWUI يستخرج النص → تقطيع (1000/100) → تضمين **all-MiniLM-L6-v2 (384) محلّياً داخل OWUI** → Chroma → استرجاع top-k (3) → حقن المقاطع + استشهادات في الدردشة.
- **حقائق (Memory):** `Settings > Personalization > Memory` → مجموعة per-user `user-memory-{id}` (بحث دلالي) → حقن كـ"User Context:".
- **⚠️ استثناء حوكمي ([ADR-025](DECISIONS.md)):** تضمين OWUI **محلّي خارج البوّابة** (ليس عبر LiteLLM، ليس Qwen3-1024) — انحراف موثّق ومقصود عن قاعدة "كل مرور موديل عبر البوّابة" (R-ARCH-10)، قابل للعكس بالإعداد.

## تبديل الموديل (مثلاً Gemini عند النشر)
سطر واحد في [config/litellm/litellm-config.yaml](../config/litellm/litellm-config.yaml) (model/api_base + المفتاح في `.env`) — R-ARCH-45 / [ADR-023](DECISIONS.md). البقية بلا تغيير.
