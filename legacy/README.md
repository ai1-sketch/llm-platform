# تشغيل موديل Qwen3-0.6B محلياً 🐍

بيئة بايثون جاهزة لتشغيل موديل **Qwen3-0.6B** على جهازك بطريقتين:

| السكربت | المحرّك | متى تستخدمه |
|---------|---------|------------|
| `run_qwen_gguf.py` | **llama.cpp** (GGUF Q8_0) | ⭐ **الأكفأ** — أقل استهلاك ذاكرة وتحميل أسرع. للاستخدام اليومي/الدردشة |
| `run_qwen.py` | Transformers + PyTorch | الأمرن — للتجارب، الوصول للـ logits، الـ fine-tuning |

> **ليش llama.cpp أكفأ؟** يشغّل نسخة مكمّمة (Q8_0 ~0.6GB) بدل الأوزان الكاملة (~1.2GB) مع
> overhead أقل بكثير من PyTorch. لموديل 0.6B الفرق ~1GB ذاكرة — حقيقي لكن صغير، فالطريقتان تعملان بسهولة.
> **ملاحظة:** vLLM ليست مناسبة هنا (لا تعمل native على ويندوز + تحجز ~90% من الـ VRAM).

## 💬 واجهة الدردشة بالمتصفح (الأسهل)

```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```
يفتح المتصفح تلقائياً على **http://127.0.0.1:7860**. واجهة دردشة كاملة مع:
- 🤖 **قائمة اختيار الموديل** — تنقّل مباشرةً بين كل ملفات `.gguf` في مجلد `models`. يُحمَّل موديل واحد في كل مرة لتوفير الـ VRAM. الموديلات المتوفّرة حالياً:
  | الموديل | الحجم | ملاحظات |
  |---------|------|---------|
  | `Qwen3-1.7B-Q8_0` | 1.75 GB | افتراضي — ذكي ومتوازن، يدعم وضع التفكير 🧠 |
  | `Qwen3-0.6B-Q8_0` | 0.61 GB | الأسرع والأخف، يدعم وضع التفكير |
  | `gemma-3-4b-it-Q4_K_M` | 2.37 GB | الأعلى جودة (Gemma 3، ~4B) — بدون وضع تفكير |
  | `gemma-2-2b-it-Q8_0` | 2.66 GB | Gemma 2 (~2B دقّة عالية) — بدون وضع تفكير |

  > ⚠️ **وضع التفكير 🧠 خاص بموديلات Qwen3 فقط** — موديلات Gemma ما إلها وضع تفكير، والسكربت يتجاهل المفتاح تلقائياً لها.
  > ملاحظة VRAM: موديلات Gemma (~2.5GB) تترك مساحة ضيّقة على كرت 6GB مشترك؛ إذا واجهت بطء، أغلق تطبيقات GPU أخرى أو استخدم موديلاً أصغر.
- بثّ مباشر للجواب (streaming)
- مفتاح **وضع التفكير** 🧠 و**إظهار خطوات التفكير** 👁️
- متحكّم بعدد التوكنات، وحفظ تلقائي لسجل المحادثات
- تعمل فوق محرّك llama.cpp الكفء على الـ GPU

> **إضافة موديل آخر:** نزّل أي ملف GGUF إلى مجلد `models` وسيظهر تلقائياً في القائمة. مثلاً:
> `huggingface-cli download Qwen/Qwen3-4B-GGUF Qwen3-4B-Q8_0.gguf --local-dir models`

## مواصفات الجهاز
- **GPU:** NVIDIA GeForce RTX 4050 Laptop (6 GB VRAM) — كافٍ تماماً (الموديل يحتاج ~1.5 GB)
- **Python:** 3.12 (داخل بيئة افتراضية `.venv`)
- **CUDA:** نسخة cu128 مدمجة داخل wheels الخاصة بـ PyTorch (لا حاجة لتثبيت CUDA Toolkit)

## التثبيت (تم تنفيذه)
```powershell
# 1) إنشاء بيئة افتراضية بـ Python 3.12
py -3.12 -m venv .venv

# 2) تفعيل البيئة
.\.venv\Scripts\Activate.ps1

# 3) تثبيت PyTorch بنسخة CUDA (مهم: من مصدر PyTorch وليس PyPI)
pip install torch --index-url https://download.pytorch.org/whl/cu128

# 4) تثبيت Transformers
pip install -r requirements.txt
```

## التشغيل
أولاً فعّل البيئة الافتراضية في كل جلسة جديدة:
```powershell
.\.venv\Scripts\Activate.ps1
```

### فحص الـ GPU
```powershell
python verify_gpu.py
```
يجب أن يطبع `CUDA available: True` واسم كرت الشاشة.

### محادثة تفاعلية
```powershell
python run_qwen.py
```
أوامر داخل المحادثة:
| الأمر | الوظيفة |
|------|---------|
| `/think` | تفعيل وضع التفكير (للرياضيات/البرمجة/المنطق) |
| `/no_think` | إيقاف وضع التفكير (دردشة عامة أسرع) |
| `/reset` | مسح سجل المحادثة |
| `/exit` | خروج |

### سؤال واحد من سطر الأوامر
```powershell
python run_qwen.py "اكتبلي دالة بايثون تحسب مضروب عدد"
python run_qwen.py --no-think "مرحبا كيفك؟"
```

## ⭐ الطريقة الأكفأ: llama.cpp (GGUF)

تم تثبيتها مسبقاً. الموديل المكمّم موجود في `models\Qwen3-0.6B-Q8_0.gguf` (~610 MB).

### التثبيت (تم تنفيذه)
```powershell
# نسخة CUDA من llama-cpp-python (wheel جاهز، بلا تصريف)
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --only-binary=:all:

# تنزيل الموديل المكمّم Q8_0 (شبه بلا خسارة جودة، مناسب للموديلات الصغيرة)
huggingface-cli download Qwen/Qwen3-0.6B-GGUF Qwen3-0.6B-Q8_0.gguf --local-dir models
```

### التشغيل
```powershell
python run_qwen_gguf.py                       # محادثة تفاعلية
python run_qwen_gguf.py "سؤالك هون"           # سؤال واحد
python run_qwen_gguf.py --no-think "مرحبا"    # دردشة سريعة
python run_qwen_gguf.py --verbose test        # لرؤية تأكيد تفريغ الطبقات على الـ GPU
```
نفس أوامر المحادثة: `/think` · `/no_think` · `/reset` · `/exit`

> **ملاحظة تقنية:** `ggml-cuda.dll` يحتاج مكتبات CUDA (cudart/cublas). السكربت يحمّلها
> تلقائياً من `torch\lib` عبر الدالة `_enable_cuda_dlls()` — لذلك يجب بقاء PyTorch مثبتاً في نفس البيئة.

## ملاحظات مهمة
- **لا تستخدم Python 3.14** لهذه البيئة — لا تتوفر wheels لـ CUDA عليها بعد، وسيعمل الموديل على الـ CPU بصمت.
- أول تشغيل ينزّل أوزان الموديل (~1.2 GB) إلى الكاش `C:\Users\Aliodeh\.cache\huggingface`. لتغيير مكان الكاش اضبط المتغير `HF_HOME`.
- **وضع التفكير** (مفعّل افتراضياً) يجعل الموديل يكتب مقطع تفكير `<think>...</think>` قبل الجواب — ممتاز للمسائل المعقّدة.
- لا تستخدم فك التشفير الجشع (greedy) مع Qwen3 — قد يسبّب تكراراً لا ينتهي. السكربت يستخدم العيّنة الموصى بها رسمياً.

## 🧪 Gemma 4 E2B (تجريبي — بيئة معزولة)

موديل **Gemma 4 E2B** يعمل في بيئة منفصلة تماماً (`.venv-gemma4` + `models-gemma4/`) ولا يمسّ إعداد v1.

```powershell
.\.venv-gemma4\Scripts\Activate.ps1
python app_gemma4.py      # واجهة ويب على http://127.0.0.1:7861
python run_gemma4.py "سؤالك"   # أو من سطر الأوامر
```

- يعمل عبر نفس نسخة llama.cpp المحفوظة (تبيّن أنها تدعم معمارية `gemma4`).
- ⚠️ **شغّل واجهة واحدة فقط** في كل مرة — الكرت 6GB مشترك (`app.py` على 7860 أو `app_gemma4.py` على 7861، مش الاثنين معاً بموديلَين محمّلَين).
- ملاحظة جودة: تنفيذ PLE في llama.cpp قد يكون ناقصاً جزئياً (issue #22243)، فاستُخدمت نسخة QAT لتقليل الأثر.
