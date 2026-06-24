# 🔖 نقطة حفظ — حالة عمل مستقرة (Qwen3 + Gemma 2/3)

نسخة شغّالة ومُختبرة بالكامل بتاريخ 2026-06-24. **ارجع إليها** إذا كسر أي تحديث لاحق (مثل تجربة Gemma 4) البيئة.

## ما الذي تحتويه هذه النسخة
- **4 موديلات** تعمل عبر llama.cpp على الـ GPU (RTX 4050): `Qwen3-0.6B`, `Qwen3-1.7B`, `gemma-3-4b-it`, `gemma-2-2b-it`
- واجهة ويب (`app.py` / Gradio) مع قائمة اختيار الموديل + سكربتات سطر الأوامر
- بيئة Python 3.12 في `.venv`

## 🔧 البيئة المثبّتة (المهمّة)
| الحزمة | النسخة | المصدر (index) |
|--------|--------|----------------|
| Python | 3.12 | `py -3.12` |
| torch | 2.11.0+cu128 | `https://download.pytorch.org/whl/cu128` |
| llama-cpp-python | **0.3.31** | `https://abetlen.github.io/llama-cpp-python/whl/cu124` |
| transformers | 5.12.1 | PyPI |
| accelerate | 1.14.0 | PyPI |
| gradio | 6.19.0 | PyPI |

النسخ الكاملة لكل الحزم في **`requirements-lock.txt`**.

---

## ↩️ كيف ترجع لهذه النسخة (الكود)
```powershell
cd C:\Users\Aliodeh\Desktop\QEWN
git checkout v1-stable      # العودة لنقطة الحفظ هذه
# أو لرؤية كل النقاط:  git tag
```

## 🛠️ إعادة بناء البيئة من الصفر (إذا تلِفت .venv)
```powershell
cd C:\Users\Aliodeh\Desktop\QEWN
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

# PyTorch بنسخة CUDA
pip install torch --index-url https://download.pytorch.org/whl/cu128

# llama.cpp — من النسخة المحفوظة محلياً (مضمونة 100%):
pip install wheels\llama_cpp_python-0.3.31-py3-none-win_amd64.whl --no-deps
#   أو من الإنترنت:
#   pip install llama-cpp-python==0.3.31 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --only-binary=:all:

# الباقي
pip install transformers==5.12.1 accelerate==1.14.0 gradio==6.19.0
```

> **ملاحظة:** الموديلات (مجلد `models`) والبيئة (`.venv`) **غير محفوظة في git** (ضخمة). الموديلات موجودة على القرص، وإذا فُقدت تُعاد بأوامر التنزيل في `README.md`.

---

## ⭐ الطريقة الآمنة لتجربة Gemma 4 (دون كسر هذه النسخة)
Gemma 4 يحتاج نسخة أحدث من `llama-cpp-python`. **بدل تحديثها في نفس البيئة** (ومخاطرة كسر الموديلات الحالية)، أنشئ **بيئة منفصلة** — هكذا تبقى `.venv` الحالية سليمة دائماً:
```powershell
py -3.12 -m venv .venv-gemma4
.\.venv-gemma4\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -U llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --only-binary=:all:
pip install gradio transformers accelerate
```
إذا نجح Gemma 4 هناك، ممتاز. إذا فشل، احذف `.venv-gemma4` فقط — ولا شيء تأثّر.

## ▶️ تشغيل هذه النسخة
```powershell
.\.venv\Scripts\Activate.ps1
python app.py        # الواجهة:  http://127.0.0.1:7860
```
