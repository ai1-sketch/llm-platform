"""فحص ثوابت المعمارية على compose — حوكمة قابلة للتنفيذ (ADR-026).

يحوّل ثوابت كانت تُفحَص بالعين إلى فحص آليّ في CI:
- R-ARCH-31: أسماء خدمات Docker ضمن القائمة المعتمدة (4 خدمات).
- R-ARCH-24: لا تكشف منفذاً سوى الواجهة (`open-webui`).
- R-LAW-06: منفذ الواجهة يربط على 127.0.0.1 افتراضياً (لا 0.0.0.0).

يخرج بـ 1 عند أي خرق مع رسالة واضحة تسمّي القاعدة (الخطأ يُعلن عن نفسه — R-ERR).
"""

import pathlib
import sys

import yaml

COMPOSE = pathlib.Path(__file__).resolve().parents[2] / "compose" / "docker-compose.yml"
ALLOWED = {"open-webui", "litellm", "llamacpp", "postgres"}  # R-ARCH-31
PUBLIC = "open-webui"  # الخدمة الوحيدة المسموح لها بكشف منفذ (R-ARCH-24)


def check(data: dict) -> list[str]:
    services = data.get("services") or {}
    errors: list[str] = []

    extra = set(services) - ALLOWED
    if extra:
        errors.append(f"R-ARCH-31: أسماء خدمات خارج القائمة المعتمدة: {sorted(extra)}")

    for name, svc in services.items():
        ports = (svc or {}).get("ports") or []
        if ports and name != PUBLIC:
            errors.append(f"R-ARCH-24: الخدمة '{name}' تكشف منفذاً (المسموح: {PUBLIC} فقط)")
        if ports and name == PUBLIC:
            bad = [p for p in ports if "127.0.0.1" not in str(p) and "OPENWEBUI_BIND" not in str(p)]
            if bad:
                errors.append(f"R-LAW-06: منفذ {PUBLIC} لا يربط على 127.0.0.1 افتراضياً: {bad}")
    return errors


def main() -> int:
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    errors = check(data)
    if errors:
        print("INVARIANTS FAILED:", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        return 1
    print(f"INVARIANTS OK — services={sorted(data.get('services') or {})} · public={PUBLIC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
