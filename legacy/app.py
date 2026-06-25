r"""
واجهة دردشة لموديلات Qwen3 عبر المتصفح (Gradio) — تعمل فوق llama.cpp (GGUF) على الـ GPU.
تدعم اختيار الموديل من قائمة (أي ملف .gguf داخل مجلد models).

التشغيل:
    .\.venv\Scripts\Activate.ps1
    python app.py
ثم افتح المتصفح على:  http://127.0.0.1:7860
"""
import os
import re
import sys
import gc
import glob
import ctypes
import importlib.util

# فرض ترميز UTF-8 لإخراج العربية على ويندوز (الافتراضي cp1252)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _enable_cuda_dlls():
    """تحميل مكتبات CUDA مسبقاً من torch/lib (يحتاجها ggml-cuda.dll) قبل استيراد llama_cpp."""
    spec = importlib.util.find_spec("torch")
    if not (spec and spec.origin):
        return
    torch_lib = os.path.join(os.path.dirname(spec.origin), "lib")
    if not os.path.isdir(torch_lib):
        return
    os.add_dll_directory(torch_lib)
    for name in ("cudart64_12.dll", "cublas64_12.dll", "cublasLt64_12.dll"):
        path = os.path.join(torch_lib, name)
        if os.path.exists(path):
            try:
                ctypes.CDLL(path)
            except OSError:
                pass


_enable_cuda_dlls()

import gradio as gr
from llama_cpp import Llama

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def list_models():
    """كل ملفات .gguf داخل مجلد models."""
    return [os.path.basename(p) for p in sorted(glob.glob(os.path.join(MODELS_DIR, "*.gguf")))]


# ── تحميل ذكي بخانة واحدة: موديل واحد محمّل في الذاكرة في كل لحظة (يوفّر الـ VRAM) ──
_current = {"name": None, "llm": None}


def get_llm(model_file):
    """يُرجع موديلاً محمّلاً؛ يحرّر السابق عند تغيير الاختيار."""
    if _current["name"] == model_file and _current["llm"] is not None:
        return _current["llm"]
    # تحرير الموديل السابق من الـ VRAM
    if _current["llm"] is not None:
        try:
            _current["llm"].close()
        except Exception:
            pass
        _current["llm"] = None
        _current["name"] = None
        gc.collect()
    path = os.path.join(MODELS_DIR, model_file)
    print(f"... جاري تحميل {model_file} على الـ GPU")
    # n_ctx=4096: سياق كافٍ للدردشة مع توفير الـ VRAM على كرت 6GB مشترك
    llm = Llama(model_path=path, n_gpu_layers=-1, n_ctx=4096, verbose=False)
    _current["name"] = model_file
    _current["llm"] = llm
    print(f"... {model_file} جاهز ✓")
    return llm


def _to_text(content):
    """تحويل محتوى الرسالة إلى نص (قد يأتي كقائمة أجزاء في Gradio 6)."""
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


def _clean_history_item(content):
    """إزالة مقاطع/اقتباسات التفكير من ردود سابقة قبل إرسالها للموديل (توصية Qwen)."""
    content = _THINK_BLOCK.sub("", content)
    content = re.sub(r"^>.*$", "", content, flags=re.MULTILINE)
    return content.strip()


def _format(raw, show_thinking):
    """تنسيق المخرجات: التفكير كاقتباس مميّز، والجواب عادي تحته."""
    if "<think>" not in raw:
        return raw
    if "</think>" in raw:
        think, _, answer = raw.partition("</think>")
        think = think.replace("<think>", "").strip()
        answer = answer.strip()
        if show_thinking and think:
            return f"> 🤔 *{think}*\n\n{answer}"
        return answer
    think = raw.replace("<think>", "").strip()
    if show_thinking:
        return f"> 🤔 *{think}*" if think else "> 🤔 *…*"
    return "🤔 يفكّر…"


def respond(message, history, model_file, thinking, show_thinking, max_tokens):
    llm = get_llm(model_file)
    is_qwen = "qwen" in model_file.lower()  # وضع التفكير ومفتاح /think خاص بـ Qwen3 فقط

    msgs = []
    for h in history:
        content = _to_text(h.get("content", ""))
        if h.get("role") == "assistant":
            content = _clean_history_item(content)
        if content:
            msgs.append({"role": h.get("role", "user"), "content": content})

    user_text = _to_text(message)
    if is_qwen:
        # مفتاح Qwen3 الناعم — لا يُضاف لموديلات أخرى (مثل Gemma) لأنها ستراه نصاً حرفياً
        user_text += " /think" if thinking else " /no_think"
    msgs.append({"role": "user", "content": user_text})

    if is_qwen:
        temperature = 0.6 if thinking else 0.7
        top_p, top_k = (0.95 if thinking else 0.8), 20
    else:
        # إعدادات Gemma الموصى بها (لا يوجد وضع تفكير)
        temperature, top_p, top_k = 1.0, 0.95, 64

    stream = llm.create_chat_completion(
        messages=msgs,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        max_tokens=int(max_tokens),
        stream=True,
    )
    raw = ""
    for chunk in stream:
        delta = chunk["choices"][0]["delta"].get("content", "")
        if delta:
            raw += delta
            yield _format(raw, show_thinking)


# ── إعداد الموديلات: التفضيل الافتراضي 1.7B إن وُجد، وإلا الأول ──
_models = list_models()
if not _models:
    raise SystemExit(f"لا توجد ملفات .gguf في {MODELS_DIR}")
_default = next((m for m in _models if "1.7B" in m), _models[0])

# تحميل مسبق للموديل الافتراضي ليكون أول رد سريعاً
get_llm(_default)

demo = gr.ChatInterface(
    fn=respond,
    title="🐍 دردشة Qwen3 — محلي على الـ GPU",
    description="نماذج محلية (Qwen3 و Gemma) تعمل بالكامل على جهازك عبر llama.cpp — بدون إنترنت وبدون تكلفة. اختر الموديل من القائمة. (وضع التفكير خاص بـ Qwen3 فقط)",
    additional_inputs=[
        gr.Dropdown(choices=_models, value=_default, label="🤖 الموديل"),
        gr.Checkbox(value=False, label="🧠 وضع التفكير (للرياضيات/البرمجة/المنطق — أبطأ)"),
        gr.Checkbox(value=True, label="👁️ إظهار خطوات التفكير"),
        gr.Slider(128, 4096, value=1024, step=128, label="أقصى عدد توكنات للرد"),
    ],
    # كل مثال صفّ كامل: [الرسالة, الموديل, تفكير, إظهار التفكير, أقصى توكنات]
    examples=[
        ["مرحبا! عرّف عن حالك بإيجاز", _default, False, True, 1024],
        ["اكتبلي دالة بايثون تتحقق إذا الرقم أولي", _default, True, True, 1024],
        ["لخّصلي ما هي الشبكات العصبية بثلاث جمل", _default, False, True, 1024],
    ],
    cache_examples=False,
    concurrency_limit=1,
    save_history=True,
)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True)
