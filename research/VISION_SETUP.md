# تفعيل الرؤية (Vision) في llama-server لـ Gemma 4 E2B — مرجع بحثي

> مرجع لقرار [ADR-014](../docs/DECISIONS.md). بحث موثّق (منتصف 2026). ليس وثيقة حوكمة (معفى من حدّ 180 سطر).

## ملف mmproj
- يُؤخذ من **نفس عائلة/مستودع الموديل**؛ مستقل عن quant الموديل النصّي (نفس الـ projector لكل الكمّيات).
- في `unsloth/gemma-4-E2B-it-qat-GGUF` (مستودع موديلنا): `mmproj-F16.gguf` (~940MB) · `mmproj-BF16.gguf` · `mmproj-F32.gguf` (~1.9GB).
- **المختار: `mmproj-F16.gguf`** (متوازن). راقب `n_embd mismatch` عند الإقلاع (دليل عائلة خاطئة).
- ملاحظة: mmproj الـ E2B قد يكون **رؤية فقط** (بلا encoder صوت) — مفيد: يتجنّب باغ الصوت #24084.

## أعلام llama-server (من server README الرسمي)
- `--mmproj <path>` — مسار الإسقاط.
- **`--no-mmproj-offload`** — يُبقي الـ projector على **CPU** بدل GPU (يوفّر ~1GB VRAM؛ أساسي على 6GB).
- `--image-max-tokens N` — سقف توكنات الصورة → **يكبح ذروة VRAM** (الصور الكبيرة = السبب الأول للـ OOM).
- `--mtmd-batch-max-tokens N` (افتراضي 1024) · `--ctx-size N`.
- الخادم (libmtmd) يدعم الصور عبر OpenAI `/v1/chat/completions` بصيغة `image_url` (base64 data URL) منذ هجرة mtmd 2025.

## صيغة الطلب (OpenAI)
```json
{"model":"...","messages":[{"role":"user","content":[
  {"type":"text","text":"ماذا في الصورة؟"},
  {"type":"image_url","image_url":{"url":"data:image/png;base64,<B64>"}}
]}]}
```
- **LiteLLM:** يلزم `model_info: {supports_vision: True}` + بادئة `openai/` ليمرّر الصور.
- **Open WebUI:** يرسل الصور base64 لـ endpoint OpenAI تلقائياً **إذا** الموديل معلَّم بقدرة vision.

## VRAM على 6GB (القيد الأخطر)
- الموديل ~2.6–3.2GB + mmproj ~1GB (إن على GPU) + KV + **ذروة ترميز الصورة (متغيّرة، المجهول الأكبر)**.
- تخفيف بالترتيب: `--no-mmproj-offload` → `--image-max-tokens` منخفض → `--ctx-size` أصغر → `-ngl` أقل → صور أقل دقة.

## مزالق معروفة
- `n_embd mismatch` (mmproj عائلة خاطئة) — استخدم نفس العائلة.
- `gemma4uv` projector غير معروف في البُناء القديمة → **استخدم أحدث `server-cuda`**.
- SIGABRT مع encoder الصوت (#24084، أُصلح #24091) — رؤية-فقط يتجنّبه.
- انهيار عبر OWUI→LiteLLM→llama.cpp على موديل أكبر (#21420) → أحدث بناء + اختبار فعلي.

## الأمر المقترح
```
llama-server -m /models/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf \
  --mmproj /models/mmproj-F16.gguf --no-mmproj-offload \
  --image-max-tokens 256 --ctx-size 4096 -ngl 99 \
  --host 0.0.0.0 --port 8080
```

## يحتاج تأكيداً عملياً
تطابق mmproj مع متغيّر `-qat-` · ملاءمة VRAM الفعلية (ذروة الترميز) · استقرار مسار OWUI→LiteLLM للصور.

### مصادر
- llama.cpp: multimodal.md · tools/server/README.md · docker.md · Discussion #22190
- HF: unsloth/gemma-4-E2B-it(-qat)-GGUF · Issues #24084 #21402 #21420 · janhq/jan #8278
- LiteLLM vision docs · Open WebUI OpenAI-compatible docs
