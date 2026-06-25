r"""
تشغيل Gemma 4 E2B عبر llama.cpp في البيئة المعزولة .venv-gemma4 (تجريبي).
لا يمسّ إعداد v1 (.venv / models) إطلاقاً.

التشغيل:
    .\.venv-gemma4\Scripts\Activate.ps1
    python run_gemma4.py                 # محادثة تفاعلية
    python run_gemma4.py "سؤالك هون"     # سؤال واحد
    python run_gemma4.py --verbose test  # لرؤية تأكيد تفريغ الطبقات على الـ GPU

أوامر داخل المحادثة:  /reset  |  /exit
"""
import os
import sys
import glob
import ctypes
import argparse
import importlib.util

for _stream in (sys.stdout, sys.stderr, sys.stdin):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _enable_cuda_dlls():
    """تحميل مكتبات CUDA مسبقاً من torch/lib (يحتاجها ggml-cuda.dll) قبل استيراد llama_cpp."""
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

from llama_cpp import Llama

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models-gemma4")


def find_model():
    files = sorted(glob.glob(os.path.join(MODELS_DIR, "*.gguf")))
    if not files:
        sys.exit(f"لا يوجد ملف GGUF في {MODELS_DIR}")
    return files[0]


def load_model(verbose=False, n_ctx=4096):
    path = find_model()
    print(f"... جاري تحميل {os.path.basename(path)} على الـ GPU")
    llm = Llama(model_path=path, n_gpu_layers=-1, n_ctx=n_ctx, verbose=verbose)
    print("... الموديل جاهز\n")
    return llm


def stream_reply(llm, messages, max_tokens=1024):
    """إعدادات العيّنة الرسمية من Gemma (لا يوجد مفتاح /think مثل Qwen)."""
    out = llm.create_chat_completion(
        messages=messages,
        temperature=1.0,
        top_p=0.95,
        top_k=64,
        max_tokens=max_tokens,
        stream=True,
    )
    full = ""
    for chunk in out:
        delta = chunk["choices"][0]["delta"].get("content", "")
        if delta:
            full += delta
            print(delta, end="", flush=True)
    print()
    return full


def interactive(llm):
    print("=== محادثة Gemma 4 E2B (تجريبي / بيئة معزولة) ===")
    print("أوامر: /reset  |  /exit\n")
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
        messages.append({"role": "user", "content": user})
        print("Gemma> ", end="", flush=True)
        reply = stream_reply(llm, messages)
        messages.append({"role": "assistant", "content": reply})


def main():
    parser = argparse.ArgumentParser(description="تشغيل Gemma 4 E2B عبر llama.cpp (تجريبي)")
    parser.add_argument("prompt", nargs="*", help="سؤال لمرة واحدة (إذا فارغ تُفتح محادثة)")
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--n-ctx", type=int, default=4096, help="قلّله إلى 2048 إذا نفد الـ VRAM")
    parser.add_argument("--verbose", action="store_true", help="إظهار سجل llama.cpp (تأكيد الـ GPU)")
    args = parser.parse_args()

    llm = load_model(verbose=args.verbose, n_ctx=args.n_ctx)
    if args.prompt:
        print("Gemma> ", end="", flush=True)
        stream_reply(llm, [{"role": "user", "content": " ".join(args.prompt)}], max_tokens=args.max_new_tokens)
    else:
        interactive(llm)


if __name__ == "__main__":
    main()
