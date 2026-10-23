"""Testning parallel variantlari (A va B) ekvivalentligi.

1. Variantlar bo'yicha natija: bir turdagi testda (odatda kirish testi, almashlab berilganda) A va B ni topshirgan
   talabalar foizlari solishtiriladi: farq testi (mezon avtomatik tanlanadi) va TOST ekvivalentlik testi —
   |M_A − M_B| < EQUIVALENCE_MARGIN foiz punkti. Farq ahamiyatsizligi ekvivalentlikni isbotlamaydi, TOST isbotlaydi.
2. Parallel variantlar ishonchliligi: bir talaba ikkala variantni ham topshirgan bo'lsa (pilot sinov) — Pirson r va
   juftlangan solishtiruv.
3. Juft savollar qiyinligi: kirish testida (o'qitishdan oldin, bir xil sharoitda) A va B dagi bir xil raqamli
   savollarning qiyinlik indeksi (to'g'ri javob ulushi); farq ITEM_GAP dan katta bo'lsa, savolni qayta ko'rib chiqish
   tavsiya etiladi.
4. Bir xil variant: kirish va chiqish testida bir xil variantni (yoki variantsiz testni) olgan talabalar — ularda
   test qilish effekti (savollarni eslab qolish) o'sishga aralashadi.
"""
from collections import defaultdict

from competence.stats import ALPHA, describe, tost
from labs.psychometrics import pearson

from .models import Quiz, QuizAttempt
from .services import finalize_if_expired, percent

FORMS = ("A", "B")
EQUIVALENCE_MARGIN = 10  # foiz punkti: 20 savolli testda 2 ta savol
ITEM_GAP = 0.15
MIN_FORM = 3
KIND_LABELS = {"pre": "Kirish testi", "post": "Chiqish testi", "delayed": "Kechiktirilgan test"}


def _r(value, digits=3):
    return None if value is None else round(value, digits)


def _describe(values):
    result = describe(values)
    return {"n": result["n"], "mean": _r(result["mean"], 2), "sd": _r(result["sd"], 2)}


def analyse(quizzes, students):
    """quizzes — kirish/chiqish/kechiktirilgan testlar, students — tahlilga kiradigan (rozi bo'lgan) talabalar."""
    from .experiment import compare_independent, compare_paired

    quizzes = list(quizzes.prefetch_related("questions"))
    attempts = QuizAttempt.objects.filter(quiz__in=quizzes, student__in=students).select_related("quiz")
    # {tur: {variant: {talaba: [foiz, ...]}}}
    scores = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    # {variant: {savol raqami: [ulush, ...]}} — faqat kirish testi
    items = defaultdict(lambda: defaultdict(list))
    forms_of = defaultdict(lambda: defaultdict(set))
    question_order = {q.pk: (q.order, q.points) for quiz in quizzes for q in quiz.questions.all()}
    for attempt in attempts:
        attempt = finalize_if_expired(attempt)
        if not attempt.submitted_at or not attempt.max_score:
            continue
        quiz = attempt.quiz
        forms_of[attempt.student_id][quiz.kind].add(quiz.form)
        if quiz.form not in FORMS:
            continue
        scores[quiz.kind][quiz.form][attempt.student_id].append(percent(attempt))
        if quiz.kind != Quiz.Kind.PRE:
            continue
        for key, earned in (attempt.results or {}).items():
            order, points = question_order.get(int(key), (None, 0))
            if order is not None and points:
                items[quiz.form][order].append(earned / points)

    by_kind = []
    reliability = None
    for kind, label in KIND_LABELS.items():
        per_form = {form: {sid: sum(v) / len(v) for sid, v in scores[kind][form].items()} for form in FORMS}
        if not any(per_form.values()):
            continue
        a, b = list(per_form["A"].values()), list(per_form["B"].values())
        equivalence = tost(a, b, EQUIVALENCE_MARGIN) if min(len(a), len(b)) >= MIN_FORM else None
        by_kind.append({
            "kind": kind,
            "label": label,
            "A": _describe(a),
            "B": _describe(b),
            "difference": compare_independent(a, b),
            "equivalence": None if equivalence is None else {
                "diff": _r(equivalence["diff"], 2),
                "margin": EQUIVALENCE_MARGIN,
                "ci": [_r(equivalence["ci"][0], 2), _r(equivalence["ci"][1], 2)],
                "p": _r(equivalence["p"], 4),
                "equivalent": equivalence["equivalent"],
            },
        })
        both = sorted(set(per_form["A"]) & set(per_form["B"]))
        if len(both) >= MIN_FORM and (reliability is None or len(both) > reliability["n"]):
            xs, ys = [per_form["A"][sid] for sid in both], [per_form["B"][sid] for sid in both]
            reliability = {"kind": kind, "n": len(both), "r": _r(pearson(xs, ys)), "paired": compare_paired(xs, ys)}

    pairs = []
    for order in sorted(set(items["A"]) & set(items["B"])):
        p_a = sum(items["A"][order]) / len(items["A"][order])
        p_b = sum(items["B"][order]) / len(items["B"][order])
        pairs.append({
            "order": order,
            "A": _r(p_a, 2),
            "B": _r(p_b, 2),
            "n_A": len(items["A"][order]),
            "n_B": len(items["B"][order]),
            "gap": abs(p_a - p_b) > ITEM_GAP,
        })

    same_form = unknown = 0
    for kinds in forms_of.values():
        if Quiz.Kind.PRE in kinds and Quiz.Kind.POST in kinds:
            pre, post = kinds[Quiz.Kind.PRE], kinds[Quiz.Kind.POST]
            if "" in pre or "" in post:
                unknown += 1
            elif pre & post:
                same_form += 1
    return {
        "margin": EQUIVALENCE_MARGIN,
        "item_gap": ITEM_GAP,
        "alpha": ALPHA,
        "by_kind": by_kind,
        "reliability": reliability,
        "items": pairs,
        "same_form": same_form,
        "without_form": unknown,
    }


def conclusions(result):
    lines = []
    for row in result["by_kind"]:
        equivalence = row["equivalence"]
        if equivalence is None:
            continue
        low, high = equivalence["ci"]
        if equivalence["equivalent"]:
            lines.append(
                f"Parallel variantlar ekvivalent ({row['label'].lower()}, TOST, ±{equivalence['margin']} foiz punkti): "
                f"farq {equivalence['diff']}, 90% ishonch oralig'i [{low}; {high}], p = {equivalence['p']:.3f}."
            )
        else:
            lines.append(
                f"Parallel variantlar ekvivalentligi isbotlanmadi ({row['label'].lower()}, TOST, ±{equivalence['margin']} foiz punkti, "
                f"p = {equivalence['p']:.3f}): pilot sinovda variantlarni tenglashtiring yoki variantni kovariata sifatida hisobga oling."
            )
    reliability = result["reliability"]
    if reliability and reliability["r"] is not None:
        lines.append(f"Parallel variantlar ishonchliligi: r = {reliability['r']} (n = {reliability['n']}).")
    gaps = [str(item["order"]) for item in result["items"] if item["gap"]]
    if gaps:
        lines.append(f"Qiyinligi variantlar orasida {round(100 * result['item_gap'])}% dan ko'p farq qiladigan juft savollar: {', '.join(gaps)}.")
    if result["same_form"] or result["without_form"]:
        lines.append(
            f"Test qilish effekti xavfi: {result['same_form'] + result['without_form']} ta talaba kirish va chiqish testida bir xil "
            "savollarni olgan (bir xil variant yoki variantsiz test). Parallel variantlardan foydalaning."
        )
    return lines
