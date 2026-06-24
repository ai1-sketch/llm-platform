r"""
واجهة ويب مخصّصة لـ Gemma 4 E2B (تجريبي) — بيئة معزولة .venv-gemma4، منفذ 7861.
لا تمسّ إعداد v1 إطلاقاً (واجهته على 7860).

التشغيل:
    .\.venv-gemma4\Scripts\Activate.ps1
    python app_gemma4.py
ثم افتح:  http://127.0.0.1:7861

ملاحظة VRAM: شغّل واجهة واحدة فقط في كل مرة (الكرت 6GB مشترك) — لا تشغّل app.py و app_gemma4.py معاً بموديلَين محمّلَين.
"""
import os
import sys
import glob
import ctypes
import importlib.util

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _enable_cuda_dlls():
    """تحميل مكتبات CUDA مسبقاً من torch/lib قبل استيراد llama_cpp."""
    spec = importlib.util.find_spec("torch")
    if not (spec and spec.origin):
        return
    lib = os.path.join(os.path.dirname(spec.origin), "lib")
    if not os.path.isdir(lib):
        return
    os.add_dll_directory(lib)
    for name in ("cudart64_12.dll", "cublas64_12.dll", "cublasLt64_12.dll"):
        p = os.path.join(lib, name)
        if os.path.exists(p):
            try:
                ctypes.CDLL(p)
            except OSError:
                pass


_enable_cuda_dlls()

import gradio as gr
from llama_cpp import Llama

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models-gemma4")


def find_model():
    files = sorted(glob.glob(os.path.join(MODELS_DIR, "*.gguf")))
    if not files:
        raise SystemExit(f"لا يوجد ملف GGUF في {MODELS_DIR}")
    return files[0]


MODEL_PATH = find_model()
MODEL_NAME = os.path.basename(MODEL_PATH)

print(f"... جاري تحميل {MODEL_NAME} على الـ GPU (لحظات)")
llm = Llama(model_path=MODEL_PATH, n_gpu_layers=-1, n_ctx=4096, verbose=False)
print("... الموديل جاهز ✓")


def _to_text(content):
    """محتوى رسالة Gradio قد يأتي كقائمة أجزاء — نحوّله إلى نص."""
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        parts = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict) and isinstance(p.get("text"), str):
                parts.append(p["text"])
        return " ".join(parts)
    return "" if content is None else str(content)


def respond(message, history, max_tokens):
    msgs = []
    for h in history:
        content = _to_text(h.get("content", ""))
        if content:
            msgs.append({"role": h.get("role", "user"), "content": content})
    msgs.append({"role": "user", "content": _to_text(message)})

    # إعدادات العيّنة الرسمية لـ Gemma (لا يوجد وضع تفكير مثل Qwen)
    stream = llm.create_chat_completion(
        messages=msgs,
        temperature=1.0,
        top_p=0.95,
        top_k=64,
        max_tokens=int(max_tokens),
        stream=True,
    )
    out = ""
    for chunk in stream:
        delta = chunk["choices"][0]["delta"].get("content", "")
        if delta:
            out += delta
            yield out


demo = gr.ChatInterface(
    fn=respond,
    title="💎 دردشة Gemma 4 E2B — محلي على الـ GPU (تجريبي)",
    description=f"الموديل: {MODEL_NAME} — يعمل بالكامل على جهازك عبر llama.cpp في بيئة معزولة. (Gemma 4 ليس له وضع تفكير على طريقة Qwen)",
    additional_inputs=[
        gr.Slider(128, 4096, value=1024, step=128, label="أقصى عدد توكنات للرد"),
    ],
    examples=[
        ["مرحبا! عرّف عن حالك بإيجاز", 1024],
        ["اكتبلي دالة بايثون تعكس سلسلة نصية", 1024],
        ["اشرحلي الفرق بين الذكاء الاصطناعي وتعلّم الآلة بإيجاز", 1024],
    ],
    cache_examples=False,
    concurrency_limit=1,
    save_history=True,
)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7861, inbrowser=True)
