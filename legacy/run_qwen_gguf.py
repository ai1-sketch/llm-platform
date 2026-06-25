"""
تشغيل Qwen3-0.6B بالطريقة الأكفأ: llama.cpp (عبر llama-cpp-python) مع نسخة Q8_0 GGUF.
استهلاك ذاكرة أقل وتحميل أسرع من Transformers، مع تفريغ كامل للطبقات على الـ GPU.

طرق الاستخدام:
  python run_qwen_gguf.py                         ->  محادثة تفاعلية
  python run_qwen_gguf.py "سؤالك هون"             ->  سؤال واحد + جواب
  python run_qwen_gguf.py --no-think "مرحبا"      ->  دردشة سريعة بدون تفكير
  python run_qwen_gguf.py --verbose ...           ->  إظهار سجل llama.cpp (للتأكد من تفريغ الطبقات على الـ GPU)

أوامر داخل المحادثة:  /think  |  /no_think  |  /reset  |  /exit
"""
import os
import re
import sys
import argparse

# فرض ترميز UTF-8 لإخراج/إدخال العربية على ويندوز (الافتراضي cp1252)
for _stream in (sys.stdout, sys.stderr, sys.stdin):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _enable_cuda_dlls():
    """ggml-cuda.dll يعتمد على cudart/cublas (نسخة CUDA 12). نحمّلها مسبقاً بالمسار
    الكامل من torch/lib قبل استيراد llama_cpp، لضمان إيجادها — بدون استيراد torch كاملاً."""
    import importlib.util
    import ctypes
    spec = importlib.util.find_spec("torch")
    if not (spec and spec.origin):
        return
    torch_lib = os.path.join(os.path.dirname(spec.origin), "lib")
    if not os.path.isdir(torch_lib):
        return
    os.add_dll_directory(torch_lib)
    # الترتيب مهم: cudart أولاً ثم cublas ثم cublasLt (تعتمد على بعضها)
    for name in ("cudart64_12.dll", "cublas64_12.dll", "cublasLt64_12.dll"):
        path = os.path.join(torch_lib, name)
        if os.path.exists(path):
            try:
                ctypes.CDLL(path)
            except OSError:
                pass


_enable_cuda_dlls()

from llama_cpp import Llama

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
IS_QWEN = True  # يُضبط في main حسب الموديل؛ مفتاح /think خاص بـ Qwen3 فقط


def _available_models():
    import glob
    return [os.path.basename(p) for p in sorted(glob.glob(os.path.join(MODELS_DIR, "*.gguf")))]


def resolve_model(name=None):
    """يحدّد ملف الموديل: من --model (اسم كامل أو جزء منه)، وإلا الافتراضي (يفضّل 1.7B)."""
    models = _available_models()
    if not models:
        sys.exit(f"لا توجد ملفات .gguf في {MODELS_DIR}\nنزّل موديلاً، مثلاً:\n"
                 f'  huggingface-cli download Qwen/Qwen3-1.7B-GGUF Qwen3-1.7B-Q8_0.gguf --local-dir models')
    if name:
        matches = [m for m in models if name.lower() in m.lower()]
        if not matches:
            sys.exit(f"لم يُطابق '--model {name}' أي ملف.\nالمتاح: {', '.join(models)}")
        return matches[0]
    return next((m for m in models if "1.7B" in m), models[0])


def load_model(model_file, verbose=False, n_ctx=4096):
    path = os.path.join(MODELS_DIR, model_file)
    print(f"... جاري تحميل {model_file} (تفريغ كامل على الـ GPU)")
    llm = Llama(
        model_path=path,
        n_gpu_layers=-1,   # -1 = تفريغ كل الطبقات على الـ RTX 4050 (يركب بسهولة)
        n_ctx=n_ctx,       # سياق صغير = KV cache صغير = أقل استهلاك للـ VRAM
        verbose=verbose,   # True يُظهر سطر "offloaded N/N layers to GPU"
    )
    print("... الموديل جاهز\n")
    return llm


def stream_reply(llm, messages, enable_thinking, max_tokens=2048):
    """يولّد الجواب بشكل streaming. الموديل يطبّق قالب المحادثة المدمج في GGUF تلقائياً."""
    if IS_QWEN:
        # إعدادات العيّنة الرسمية من Qwen — لا تستخدم greedy
        temperature = 0.6 if enable_thinking else 0.7
        top_p, top_k = (0.95 if enable_thinking else 0.8), 20
    else:
        # إعدادات Gemma الموصى بها (لا يوجد وضع تفكير)
        temperature, top_p, top_k = 1.0, 0.95, 64

    stream = llm.create_chat_completion(
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        max_tokens=max_tokens,
        stream=True,
    )
    full = ""
    for chunk in stream:
        delta = chunk["choices"][0]["delta"].get("content", "")
        if delta:
            full += delta
            print(delta, end="", flush=True)
    print()
    return full


def build_user_message(text, enable_thinking):
    """يضيف مفتاح Qwen3 الناعم /think أو /no_think (لموديلات Qwen فقط)."""
    if IS_QWEN:
        text += " /think" if enable_thinking else " /no_think"
    return {"role": "user", "content": text}


def interactive(llm, enable_thinking):
    print("=== محادثة GGUF / llama.cpp ===")
    print("أوامر: /think  |  /no_think  |  /reset  |  /exit")
    print(f"وضع التفكير حالياً: {'مفعّل' if enable_thinking else 'متوقّف'}\n")
    messages = []
    while True:
        try:
            user = input("أنت> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nمع السلامة 👋")
            break
        if not user:
            continue
        if user == "/exit":
            print("مع السلامة 👋")
            break
        if user == "/reset":
            messages = []
            print("(تم مسح سجل المحادثة)\n")
            continue
        if user == "/think":
            enable_thinking = True
            print("(وضع التفكير: مفعّل)\n")
            continue
        if user == "/no_think":
            enable_thinking = False
            print("(وضع التفكير: متوقّف)\n")
            continue

        messages.append(build_user_message(user, enable_thinking))
        print("Qwen> ", end="", flush=True)
        reply = stream_reply(llm, messages, enable_thinking)
        # نخزّن الجواب بدون مقطع التفكير (توصية Qwen لتاريخ المحادثة)
        messages.append({"role": "assistant", "content": _THINK_BLOCK.sub("", reply).strip()})


def main():
    parser = argparse.ArgumentParser(description="تشغيل موديلات Qwen3 عبر llama.cpp (GGUF)")
    parser.add_argument("prompt", nargs="*", help="سؤال لمرة واحدة (إذا فارغ تُفتح محادثة)")
    parser.add_argument("--model", default=None, help="اسم ملف الموديل أو جزء منه (مثل 1.7B). الافتراضي يفضّل 1.7B")
    parser.add_argument("--no-think", action="store_true", help="إيقاف وضع التفكير")
    parser.add_argument("--max-new-tokens", type=int, default=2048)
    parser.add_argument("--verbose", action="store_true", help="إظهار سجل llama.cpp (تأكيد الـ GPU)")
    args = parser.parse_args()

    enable_thinking = not args.no_think
    model_file = resolve_model(args.model)
    global IS_QWEN
    IS_QWEN = "qwen" in model_file.lower()
    llm = load_model(model_file, verbose=args.verbose)

    if args.prompt:
        messages = [build_user_message(" ".join(args.prompt), enable_thinking)]
        print("Qwen> ", end="", flush=True)
        stream_reply(llm, messages, enable_thinking, max_tokens=args.max_new_tokens)
    else:
        interactive(llm, enable_thinking)


if __name__ == "__main__":
    main()
