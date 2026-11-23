"""Koddagi tr("...") va N_("...") matnlarini yig'adi: lug'atlar (locale/*.json) to'liqligini tekshirish uchun.

    python -m config.i18n_keys            — yetishmayotgan/ortiqcha kalitlar (xato bo'lsa exit 1)
    python -m config.i18n_keys --keys     — barcha kalitlar JSON ko'rinishida
"""

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"migrations", "media", "staticfiles", "__pycache__", "venv", ".venv"}
MARKERS = {"tr", "N_"}


def _literals(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.IfExp):
        branches = [_literals(node.body), _literals(node.orelse)]
        return branches[0] + branches[1] if all(b is not None for b in branches) else None
    return None


def collect_keys() -> dict[str, str]:
    """{kalit: birinchi uchragan joy}"""
    keys: dict[str, str] = {}
    for path in sorted(ROOT.rglob("*.py")):
        if SKIP_DIRS & set(path.relative_to(ROOT).parts) or path.name.startswith("tests"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in MARKERS and node.args:
                for text in _literals(node.args[0]) or []:
                    if re.search(r"[A-Za-z]", text):
                        keys.setdefault(text, f"{path.relative_to(ROOT)}:{node.lineno}")
    return keys


def problems() -> list[str]:
    keys = collect_keys()
    found = []
    names = lambda s: sorted(re.findall(r"\{(\w+)\}", s))  # noqa: E731
    for lang in ("en", "ru"):
        words = json.loads((ROOT / "locale" / f"{lang}.json").read_text(encoding="utf-8"))
        found += [f"{lang}: tarjimasiz {key!r} ({where})" for key, where in keys.items() if not words.get(key)]
        found += [f"{lang}: o'rinlar mos emas {key!r}" for key in keys if words.get(key) and names(key) != names(words[key])]
        found += [f"{lang}: ortiqcha {key!r}" for key in words if key not in keys]
    return found


if __name__ == "__main__":
    if "--keys" in sys.argv:
        print(json.dumps(list(collect_keys()), ensure_ascii=False, indent=1))
        sys.exit(0)
    issues = problems()
    print("\n".join(issues[:50]) or "OK")
    sys.exit(1 if issues else 0)
