"""فحص ثوابت المعمارية على compose — حوكمة قابلة للتنفيذ (ADR-026).

يحوّل ثوابت كانت تُفحَص بالعين إلى فحص آليّ في CI:
- R-ARCH-31: أسماء خدمات Docker ⊆ القائمة المعتمدة (5 أساسية **مطلوبة** + 2 مراقبة **اختيارية قابلة للحذف** — ADR-031/033).
- R-ARCH-24: لا تكشف منفذاً سوى الواجهة (`open-webui`) ولوحة المراقبة المحلية (`grafana`، ADR-031).
- R-LAW-06: منفذ الواجهة يربط على 127.0.0.1 افتراضياً (لا 0.0.0.0).
- R-ARCH-40: كل صورة مثبّتة بـ @sha256: (إعادة إنتاج حتمية — لا وسوم متغيّرة).
- R-LAW-03/R-ARCH-02/20: لا أسرار/بيانات/نماذج متتبَّعة في git (‎.env، backups/، models/).

يخرج بـ 1 عند أي خرق مع رسالة واضحة تسمّي القاعدة (الخطأ يُعلن عن نفسه — R-ERR).
"""

import pathlib
import shutil
import subprocess
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "compose" / "docker-compose.yml"
# R-ARCH-31 — 5 خدمات أساسية **مطلوبة** (vllm منذ ADR-028؛ قاعدتان مخصّصتان منذ ADR-030)
CORE = {
    "open-webui",
    "litellm",
    "vllm",
    "postgres-litellm",
    "postgres-openwebui",
}
# 2 خدمة مراقبة **اختيارية** (profiles: [monitoring] — ADR-031): مسموحة لكن غير مطلوبة،
# حذفها من compose لا يكسر CI — تجسيد قابلية العكس §5 التي قُبِل عليها ADR-031 (ADR-033، تدقيق 2026-07-10)
OPTIONAL = {
    "prometheus",
    "grafana",
}
ALLOWED = CORE | OPTIONAL
PUBLIC = "open-webui"  # الواجهة العامة الوحيدة (R-ARCH-24)
# خدمات يُسمح لها بكشف منفذ محلي 127.0.0.1 (R-LAW-06): الواجهة + grafana (ADR-031)
PORT_ALLOWED = {"open-webui", "grafana"}
# مسارات يجب ألا تُتتبَّع في git (R-ARCH-02): بيانات/نماذج قابلة لإعادة التوليد أو ضخمة
FORBIDDEN_TRACKED_PREFIXES = ("backups/", "models/")


def check(data: dict) -> list[str]:
    services = data.get("services") or {}
    errors: list[str] = []

    names = set(services)
    extra = names - ALLOWED
    if extra:
        errors.append(f"R-ARCH-31: أسماء خدمات خارج القائمة المعتمدة: {sorted(extra)}")
    # الأساسية فقط مطلوبة؛ المراقبة (OPTIONAL) قابلة للحذف بلا كسر CI (ADR-031 §5 / ADR-033)
    missing_core = CORE - names
    if missing_core:
        errors.append(f"R-ARCH-31: خدمات أساسية غائبة عن compose: {sorted(missing_core)}")

    for name, svc in services.items():
        svc = svc or {}
        image = svc.get("image")
        if image and "@sha256:" not in str(image):
            errors.append(f"R-ARCH-40: صورة الخدمة '{name}' غير مثبّتة بـ @sha256: {image}")
        ports = svc.get("ports") or []
        if ports and name not in PORT_ALLOWED:
            errors.append(f"R-ARCH-24: '{name}' تكشف منفذاً (المسموح: {sorted(PORT_ALLOWED)})")
        if ports and name in PORT_ALLOWED:
            # يجب أن يتضمّن تعريف المنفذ 127.0.0.1 حرفياً (كافتراضي للربط)؛
            # مجرّد ذكر اسم المتغيّر لا يكفي — افتراضي 0.0.0.0 خرقٌ لـ R-LAW-06 (تدقيق 2026-07-02)
            bad = [p for p in ports if "127.0.0.1" not in str(p)]
            if bad:
                errors.append(f"R-LAW-06: منفذ '{name}' لا يربط على 127.0.0.1 افتراضياً: {bad}")
    return errors


def check_git_tracking() -> list[str]:
    """R-LAW-03/R-ARCH-02: لا أسرار/بيانات متتبَّعة. أفضل-جهد: يتخطّى بتحذير إن غاب git."""
    if shutil.which("git") is None:
        print("WARN: git غير متاح — تخطّي فحص الملفّات المتتبَّعة", file=sys.stderr)
        return []
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"WARN: git ls-files فشل ({exc}) — تخطّي الفحص", file=sys.stderr)
        return []

    errors: list[str] = []
    for path in result.stdout.splitlines():
        p = path.strip()
        if not p:
            continue
        base = p.rsplit("/", 1)[-1]
        if base == ".env":  # ملف أسرار فعلي (‎.env.example مسموح)
            errors.append(f"R-LAW-03: ملف أسرار متتبَّع في git: {p}")
        if p.startswith(FORBIDDEN_TRACKED_PREFIXES):
            errors.append(f"R-ARCH-02: مسار يجب ألا يُتتبَّع (بيانات/نماذج): {p}")
    return errors


def main() -> int:
    # رسائلنا عربية: على Windows (cp1252) الفشل كان يطمر الخطأ الأصلي بـ UnicodeEncodeError
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    errors = check(data) + check_git_tracking()
    if errors:
        print("INVARIANTS FAILED:", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        return 1
    print(f"INVARIANTS OK — services={sorted(data.get('services') or {})} · public={PUBLIC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
