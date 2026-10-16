"""Normallashtirish laboratoriyasi: funksional bog'liqliklar (FB) bo'yicha algoritmik tekshiruv.

O'qituvchi munosabat atributlarini, FB larni va maqsad normal formani (3NF yoki BCNF) beradi. Talaba:
1) barcha nomzod kalitlarni, 2) munosabatning hozirgi (eng yuqori) normal formasini, 3) maqsad formadagi
dekompozitsiyani topadi. Hammasi AI'siz, hisoblab tekshiriladi:
- atributlar yopilmasi (closure), nomzod kalitlar — barcha to'plamlarni ko'rib chiqish (atributlar <= 12 ta);
- normal forma: 2NF (qisman bog'liqlik yo'q), 3NF, BCNF;
- dekompozitsiya: har bir jadval maqsad formada (FB lar jadvalga proyeksiya qilinadi), yo'qotishsiz birlashish
  (chase testi) va 3NF uchun bog'liqliklarning saqlanishi.
Talabaga farqlar aytiladi, lekin to'g'ri javob (kalitlar, jadvallar) oshkor qilinmaydi.
"""
import re
from itertools import combinations

MAX_ATTRIBUTES = 12
MAX_FDS = 30
MAX_RELATIONS = 10
NORMAL_FORMS = ("1NF", "2NF", "3NF", "BCNF")
TARGETS = ("3NF", "BCNF")
NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


class NormError(ValueError):
    """Topshiriq yoki javob formati noto'g'ri (talabaga ko'rsatiladigan matn bilan)."""


# ---------- Formatni o'qish ----------


def _names(text, known=None, what="atribut"):
    names = [part.strip().lower() for part in str(text).split(",") if part.strip()]
    for name in names:
        if not NAME.match(name):
            raise NormError(f"«{name}» — noto'g'ri {what} nomi (lotin harflari, raqam va _).")
        if known is not None and name not in known:
            raise NormError(f"«{name}» atributi munosabatda yo'q.")
    if len(set(names)) != len(names):
        raise NormError(f"{what.capitalize()}lar takrorlangan: {', '.join(names)}.")
    return names


def parse_task(attributes_text, fds_text, target):
    """O'qituvchi kiritgan matnni tekshiradi. Qaytaradi: {"attributes", "fds": [{"lhs", "rhs"}], "target"}."""
    attributes = _names(attributes_text)
    if not 2 <= len(attributes) <= MAX_ATTRIBUTES:
        raise NormError(f"Atributlar soni 2 dan {MAX_ATTRIBUTES} gacha bo'lsin.")
    fds = []
    for line in str(fds_text).splitlines():
        if not line.strip():
            continue
        if "->" not in line:
            raise NormError(f"«{line.strip()}» qatorida -> yo'q. Format: a, b -> c")
        left, right = line.split("->", 1)
        lhs, rhs = _names(left, attributes), _names(right, attributes)
        if not lhs or not rhs:
            raise NormError(f"«{line.strip()}» qatorining ikki tomoni ham to'ldirilsin.")
        fds.append({"lhs": sorted(lhs), "rhs": sorted(rhs)})
    if not 1 <= len(fds) <= MAX_FDS:
        raise NormError(f"Funksional bog'liqliklar soni 1 dan {MAX_FDS} gacha bo'lsin.")
    if target not in TARGETS:
        raise NormError("Maqsad normal forma 3NF yoki BCNF bo'lsin.")
    return {"attributes": attributes, "fds": fds, "target": target}


def task_text(task):
    lines = [f"R({', '.join(task['attributes'])})", "Funksional bog'liqliklar:"]
    lines += [f"  {', '.join(fd['lhs'])} -> {', '.join(fd['rhs'])}" for fd in task["fds"]]
    lines.append(f"Maqsad: {task['target']}")
    return "\n".join(lines)


def parse_answer(data, task):
    """Talaba javobi: {"keys": [[...]], "normal_form": "2NF", "decomposition": [[...]]} (ro'yxatlar yoki "a, b")."""
    if not isinstance(data, dict):
        raise NormError("Javob noto'g'ri formatda.")
    known = set(task["attributes"])

    def name_sets(items, what):
        if not isinstance(items, list) or len(items) > MAX_RELATIONS:
            raise NormError(f"{what}: ro'yxat {MAX_RELATIONS} tadan oshmasin.")
        result = []
        for item in items:
            text = ", ".join(map(str, item)) if isinstance(item, list) else str(item)
            # "R1(a, b)" yoki "{a, b}" ko'rinishida yozilsa ham qabul qilinadi
            if "(" in text:
                text = text[text.index("(") + 1 :].rstrip().rstrip(")")
            text = text.strip().strip("{}")
            names = _names(text, known)
            if names:
                result.append(sorted(names))
        return result

    keys = name_sets(data.get("keys", []), "Kalitlar")
    decomposition = name_sets(data.get("decomposition", []), "Jadvallar")
    normal_form = data.get("normal_form")
    if normal_form not in NORMAL_FORMS:
        raise NormError("Hozirgi normal formani tanlang.")
    if not keys:
        raise NormError("Kamida bitta nomzod kalitni yozing.")
    if not decomposition:
        raise NormError("Dekompozitsiyani (yangi jadvallarni) yozing.")
    return {"keys": keys, "normal_form": normal_form, "decomposition": decomposition}


def answer_text(answer):
    """Javobning o'qiladigan ko'rinishi (o'qituvchi sahifasi, o'xshashlik va eksport uchun)."""
    lines = ["Nomzod kalitlar: " + "; ".join("{" + ", ".join(key) + "}" for key in answer["keys"])]
    lines.append(f"Hozirgi normal forma: {answer['normal_form']}")
    lines.append("Dekompozitsiya:")
    lines += [f"  R{index}({', '.join(relation)})" for index, relation in enumerate(answer["decomposition"], start=1)]
    return "\n".join(lines)


# ---------- Algoritmlar ----------


def _fds(task):
    return [(frozenset(fd["lhs"]), frozenset(fd["rhs"])) for fd in task["fds"]]


def closure(attributes, fds):
    result = set(attributes)
    changed = True
    while changed:
        changed = False
        for lhs, rhs in fds:
            if lhs <= result and not rhs <= result:
                result |= rhs
                changed = True
    return frozenset(result)


def _subsets(attributes, proper=False):
    items = sorted(attributes)
    top = len(items) - 1 if proper else len(items)
    for size in range(top + 1):
        for combo in combinations(items, size):
            yield frozenset(combo)


def candidate_keys(attributes, fds):
    """Minimal superkalitlar (kichigidan boshlab ko'rib chiqiladi)."""
    attributes = frozenset(attributes)
    keys = []
    for subset in _subsets(attributes):
        if any(key <= subset for key in keys):
            continue
        if closure(subset, fds) >= attributes:
            keys.append(subset)
    return keys


def project(fds, relation):
    """FB larning jadvalga proyeksiyasi: har bir X ⊆ R uchun X -> (X+ ∩ R) \\ X."""
    relation = frozenset(relation)
    projected = []
    for subset in _subsets(relation):
        implied = (closure(subset, fds) & relation) - subset
        if subset and implied:
            projected.append((subset, implied))
    return projected


def normal_form(attributes, fds):
    """Munosabatning eng yuqori normal formasi (1NF dan BCNF gacha)."""
    attributes = frozenset(attributes)
    keys = candidate_keys(attributes, fds)
    prime = frozenset().union(*keys)
    nonprime = attributes - prime

    # 2NF: hech bir asosiy bo'lmagan atribut kalitning qismiga bog'liq emas
    for key in keys:
        for part in _subsets(key, proper=True):
            if part and (closure(part, fds) - part) & nonprime:
                return "1NF"
    bcnf = third = True
    for lhs, rhs in project(fds, attributes):
        if closure(lhs, fds) >= attributes:
            continue
        bcnf = False
        if not rhs <= prime:
            third = False
    if bcnf:
        return "BCNF"
    return "3NF" if third else "2NF"


def satisfies(attributes, fds, target):
    rank = NORMAL_FORMS.index
    return rank(normal_form(attributes, fds)) >= rank(target)


def lossless(attributes, fds, relations):
    """Chase testi: jadvalda bitta qator to'liq "a" belgilariga aylansa — yo'qotishsiz."""
    attributes = sorted(attributes)
    rows = [{attr: ("a" if attr in relation else f"b{index}") for attr in attributes} for index, relation in enumerate(relations)]
    changed = True
    while changed:
        changed = False
        for lhs, rhs in fds:
            groups = {}
            for row in rows:
                groups.setdefault(tuple(row[attr] for attr in sorted(lhs)), []).append(row)
            for group in groups.values():
                if len(group) < 2:
                    continue
                for attr in rhs:
                    values = {row[attr] for row in group}
                    if len(values) > 1:
                        best = "a" if "a" in values else min(values)
                        for row in group:
                            if row[attr] != best:
                                row[attr] = best
                                changed = True
        if any(all(value == "a" for value in row.values()) for row in rows):
            return True
    return False


def preserves(fds, relations):
    """Har bir FB jadvallardagi proyeksiyalar orqali kelib chiqadimi."""
    lost = []
    for lhs, rhs in fds:
        result = set(lhs)
        changed = True
        while changed:
            changed = False
            for relation in relations:
                relation = frozenset(relation)
                added = (closure(result & relation, fds) & relation) - result
                if added:
                    result |= added
                    changed = True
        if not rhs <= result:
            lost.append((lhs, rhs))
    return lost


# ---------- Tekshirish ----------


def _set_text(names):
    return "{" + ", ".join(sorted(names)) + "}"


def check(task, answer):
    """Qaytaradi: {"differences": [...], "ratio": 0..1}. Ratio — to'g'ri bajarilgan qismlar ulushi."""
    attributes = frozenset(task["attributes"])
    fds = _fds(task)
    keys = candidate_keys(attributes, fds)
    differences = []
    parts = {"keys": True, "normal_form": True, "decomposition": True}

    # 1. Nomzod kalitlar: noto'g'ri berilganlari aytiladi, yetishmaganlari esa faqat soni bilan
    given = [frozenset(key) for key in answer["keys"]]
    for key in given:
        if closure(key, fds) < attributes:
            differences.append(f"{_set_text(key)} — kalit emas: uning yopilmasi barcha atributlarni qamrab olmaydi.")
            parts["keys"] = False
        elif key not in keys:
            differences.append(f"{_set_text(key)} — superkalit, lekin minimal emas: undan atribut olib tashlash mumkin.")
            parts["keys"] = False
    missing = [key for key in keys if key not in given]
    if missing:
        differences.append(
            f"Barcha nomzod kalitlar topilmadi: yana {len(missing)} ta kalit bor. Har bir atribut to'plamining "
            "yopilmasini hisoblab ko'ring."
        )
        parts["keys"] = False

    # 2. Hozirgi normal forma
    actual = normal_form(attributes, fds)
    if answer["normal_form"] != actual:
        direction = "yuqori" if NORMAL_FORMS.index(answer["normal_form"]) > NORMAL_FORMS.index(actual) else "past"
        differences.append(
            f"Hozirgi normal forma noto'g'ri: siz ko'rsatgan {answer['normal_form']} haqiqiysidan {direction}. "
            "Qisman (kalit qismiga) va tranzitiv bog'liqliklarni tekshiring."
        )
        parts["normal_form"] = False

    # 3. Dekompozitsiya
    relations = [frozenset(relation) for relation in answer["decomposition"]]
    covered = frozenset().union(*relations)
    if covered != attributes:
        differences.append(f"Dekompozitsiya barcha atributlarni qamramaydi: {_set_text(attributes - covered)} yo'q.")
        parts["decomposition"] = False
    for index, relation in enumerate(relations, start=1):
        projected = project(fds, relation)
        if not satisfies(relation, projected, task["target"]):
            violation = next(
                (
                    (lhs, rhs)
                    for lhs, rhs in projected
                    if not closure(lhs, projected) >= relation
                ),
                None,
            )
            reason = (
                f": {_set_text(violation[0])} -> {_set_text(violation[1])} bog'liqligida chap tomon bu jadvalda kalit emas"
                if violation
                else ""
            )
            differences.append(f"R{index}{_set_text(relation)} {task['target']} da emas{reason}.")
            parts["decomposition"] = False
    if covered == attributes and not lossless(attributes, fds, relations):
        differences.append(
            "Dekompozitsiya yo'qotishli: jadvallarni qayta birlashtirganda ortiqcha (soxta) qatorlar paydo bo'ladi. "
            "Jadvallar umumiy atributlar orqali kalit bilan bog'lanishi kerak."
        )
        parts["decomposition"] = False
    if task["target"] == "3NF":
        for lhs, rhs in preserves(fds, relations):
            differences.append(
                f"{_set_text(lhs)} -> {_set_text(rhs)} bog'liqligi saqlanmadi: uni tekshirish uchun jadvallarni "
                "birlashtirish kerak bo'ladi (3NF dekompozitsiyasi bog'liqliklarni saqlashi shart)."
            )
            parts["decomposition"] = False

    weights = {"keys": 0.3, "normal_form": 0.2, "decomposition": 0.5}
    ratio = sum(weight for part, weight in weights.items() if parts[part])
    return {"differences": differences, "ratio": round(ratio, 2)}


def reference_solution(task):
    """O'qituvchi sahifasi uchun: kalitlar, hozirgi forma va maqsad formadagi (sintez/BCNF) dekompozitsiya."""
    attributes = frozenset(task["attributes"])
    fds = _fds(task)
    keys = candidate_keys(attributes, fds)
    relations = bcnf_decompose(attributes, fds) if task["target"] == "BCNF" else synthesize_3nf(attributes, fds, keys)
    return {
        "keys": [sorted(key) for key in keys],
        "normal_form": normal_form(attributes, fds),
        "decomposition": [sorted(relation) for relation in relations],
    }


def minimal_cover(fds):
    single = [(lhs, frozenset([attr])) for lhs, rhs in fds for attr in rhs if attr not in lhs]
    reduced = []
    for lhs, rhs in single:
        for attr in sorted(lhs):
            smaller = lhs - {attr}
            if smaller and rhs <= closure(smaller, single):
                lhs = smaller
        reduced.append((lhs, rhs))
    cover = list(dict.fromkeys(reduced))
    for fd in list(cover):
        rest = [other for other in cover if other != fd]
        if fd[1] <= closure(fd[0], rest):
            cover = rest
    return cover


def synthesize_3nf(attributes, fds, keys):
    groups = {}
    for lhs, rhs in minimal_cover(fds):
        groups.setdefault(lhs, set(lhs)).update(rhs)
    relations = [frozenset(group) for group in groups.values()]
    if not any(any(key <= relation for key in keys) for relation in relations):
        relations.append(min(keys, key=lambda key: (len(key), sorted(key))))
    relations = [relation for relation in relations if not any(relation < other for other in relations)]
    used = frozenset().union(*relations) if relations else frozenset()
    if used != attributes:
        relations.append(attributes - used)
    return list(dict.fromkeys(relations))


def bcnf_decompose(attributes, fds):
    pending, result = [frozenset(attributes)], []
    while pending:
        relation = pending.pop()
        violation = next(
            ((lhs, rhs) for lhs, rhs in project(fds, relation) if not closure(lhs, fds) >= relation), None
        )
        if violation is None:
            result.append(relation)
            continue
        lhs = violation[0]
        left = closure(lhs, fds) & relation
        pending += [left, (relation - left) | lhs]
    return list(dict.fromkeys(result))
