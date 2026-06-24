"""
تشغيل موديل Qwen3-0.6B محلياً باستخدام Hugging Face Transformers + PyTorch (CUDA).

طرق الاستخدام:
  python run_qwen.py                       ->  محادثة تفاعلية
  python run_qwen.py "اشرحلي ما هي الشبكات العصبية"   ->  سؤال واحد + جواب
  python run_qwen.py --no-think "مرحبا"    ->  بدون وضع التفكير (أسرع للدردشة)

أوامر داخل المحادثة التفاعلية:
  /think      تفعيل وضع التفكير (مناسب للرياضيات/البرمجة/المنطق)
  /no_think   إيقاف وضع التفكير (دردشة عامة أسرع)
  /reset      مسح سجل المحادثة
  /exit       خروج
"""
import sys
import argparse

# فرض ترميز UTF-8 لإخراج/إدخال العربية بشكل صحيح على ويندوز (الافتراضي cp1252)
for _stream in (sys.stdout, sys.stderr, sys.stdin):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextStreamer

MODEL_NAME = "Qwen/Qwen3-0.6B"

# توكن نهاية قسم التفكير </think> — يُستخدم لفصل التفكير عن الجواب
THINK_END_TOKEN_ID = 151668


def load_model():
    print(f"... جاري تحميل {MODEL_NAME} (أول مرة يتم تنزيل ~1.2GB من Hugging Face)")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype="auto",   # يختار bf16 تلقائياً لموديلات Qwen3
        device_map="auto",    # يضع الموديل على الـ GPU إن توفّر
    )
    device = next(model.parameters()).device
    print(f"... الموديل جاهز على الجهاز: {device}\n")
    return tokenizer, model


def generate(tokenizer, model, messages, enable_thinking=True, max_new_tokens=2048, stream=True):
    """يبني الـ prompt عبر قالب المحادثة، يولّد الجواب، ويفصل التفكير عن المحتوى."""
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=enable_thinking,
    )
    inputs = tokenizer([text], return_tensors="pt").to(model.device)

    # إعدادات العيّنة الموصى بها رسمياً من Qwen — لا تستخدم greedy (do_sample=False)
    if enable_thinking:
        gen_kwargs = dict(temperature=0.6, top_p=0.95, top_k=20)
    else:
        gen_kwargs = dict(temperature=0.7, top_p=0.8, top_k=20)

    streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True) if stream else None

    generated = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        streamer=streamer,
        **gen_kwargs,
    )
    output_ids = generated[0][len(inputs.input_ids[0]):].tolist()

    # فصل قسم التفكير عن الجواب النهائي عبر موقع توكن </think>
    try:
        idx = len(output_ids) - output_ids[::-1].index(THINK_END_TOKEN_ID)
    except ValueError:
        idx = 0
    thinking = tokenizer.decode(output_ids[:idx], skip_special_tokens=True).strip("\n")
    content = tokenizer.decode(output_ids[idx:], skip_special_tokens=True).strip("\n")
    return thinking, content


def interactive(tokenizer, model, enable_thinking):
    print("=== محادثة Qwen3-0.6B ===")
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

        messages.append({"role": "user", "content": user})
        print("Qwen> ", end="", flush=True)
        _thinking, content = generate(
            tokenizer, model, messages, enable_thinking=enable_thinking, stream=True
        )
        messages.append({"role": "assistant", "content": content})
        print()


def main():
    parser = argparse.ArgumentParser(description="تشغيل موديل Qwen3-0.6B محلياً")
    parser.add_argument("prompt", nargs="*", help="سؤال لمرة واحدة (إذا فارغ تُفتح محادثة تفاعلية)")
    parser.add_argument("--no-think", action="store_true", help="إيقاف وضع التفكير")
    parser.add_argument("--max-new-tokens", type=int, default=2048, help="أقصى عدد توكنات للجواب")
    args = parser.parse_args()

    enable_thinking = not args.no_think
    tokenizer, model = load_model()

    if args.prompt:
        prompt = " ".join(args.prompt)
        messages = [{"role": "user", "content": prompt}]
        print("Qwen> ", end="", flush=True)
        generate(
            tokenizer, model, messages,
            enable_thinking=enable_thinking,
            max_new_tokens=args.max_new_tokens,
            stream=True,
        )
        print()
    else:
        interactive(tokenizer, model, enable_thinking)


if __name__ == "__main__":
    main()
