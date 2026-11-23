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


def _marked(node) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in MARKERS


def _label(node) -> bool:
    """Foydalanuvchiga ko'rinadigan yorliqqa o'xshash satr: bo'sh joyli yoki bosh harf bilan boshlangan so'z."""
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return False
    text = node.value.strip()
    return bool(re.search(r"[A-Za-z]", text)) and (" " in text or "'" in text or bool(re.match(r"[A-Z][a-z]", text)))


def unmarked_labels() -> list[str]:
    """Bir guruhdagi (lug'at qiymatlari, ro'yxat, kortejlar ro'yxatining bir ustuni, a if c else b) ba'zi yorliqlar
    tr()/N_() bilan belgilangan-u, qo'shnisi belgilanmagan bo'lsa — u tarjimaga tushmay, o'zbekcha qolib ketadi."""
    found = []
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if SKIP_DIRS & set(rel.parts) or "management" in rel.parts or path.name.startswith("tests"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            groups = []
            if isinstance(node, ast.Dict):
                groups.append(node.values)
            elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                groups.append(node.elts)
                if node.elts and all(isinstance(item, ast.Tuple) for item in node.elts):
                    width = max(len(item.elts) for item in node.elts)
                    groups += [[item.elts[i] for item in node.elts if len(item.elts) > i] for i in range(width)]
            elif isinstance(node, ast.IfExp):
                groups.append([node.body, node.orelse])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                groups.append([item.value for item in ast.walk(node) if isinstance(item, ast.Return) and item.value])
            for group in groups:
                if any(_marked(item) for item in group):
                    found += [f"belgilanmagan yorliq {item.value!r} ({rel}:{item.lineno})" for item in group if _label(item)]
    return sorted(set(found))


def problems() -> list[str]:
    keys = collect_keys()
    found = unmarked_labels()
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
