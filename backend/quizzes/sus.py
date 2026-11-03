"""SUS so'rovnomasi natijasini hisoblash (Brooke, 1996).

Har bir talaba uchun: toq fikrlar — (javob − 1), juft fikrlar — (5 − javob); yig'indi × 2,5 → 0–100.
Bitta fikr ham javobsiz qolsa, talabaning bali hisoblanmaydi (to'liqsiz javob alohida sanaladi).

Guruh bo'yicha: o'rtacha, SD, o'rtachaning 95% ishonch oralig'i (Styudent t), mediana, Cronbach α (fikrlar
yo'nalishi to'g'rilangandan keyin) va o'rtacha balning talqini:
- Sauro-Lewis egri baholash shkalasi (A+ … F; 68 — o'rtacha, C);
- Bangor va boshq. (2008) qabul qilinish oraliqlari (< 50 — qabul qilinmaydi, 50–70 — chegaraviy, ≥ 70 — qabul qilinadi);
- 68 lik o'rtacha me'yordan farq (bir tanlanmali t-test).
"""
import math

from competence.stats import _t_ppf, describe, t_two_sided_p
from labs.psychometrics import cronbach_alpha

from .models import QuizAttempt
from .services import finalize_if_expired, likert_value
from .sus_bank import SUS_ITEMS, SUS_TITLE

ITEMS = len(SUS_ITEMS)
BENCHMARK = 68.0
# Sauro va Lewis (2016) egri baholash shkalasi: (quyi chegara, baho)
GRADES = [
    (84.1, "A+"), (80.8, "A"), (78.9, "A−"), (77.2, "B+"), (74.1, "B"), (72.6, "B−"),
    (71.1, "C+"), (65.0, "C"), (62.7, "C−"), (51.7, "D"), (0.0, "F"),
]
# Bangor, Kortum va Miller (2008): qabul qilinish oraliqlari
ACCEPTABILITY = [(70.0, "qabul qilinadi"), (50.0, "chegaraviy"), (0.0, "qabul qilinmaydi")]


def _r(value, digits=2):
    return None if value is None else round(value, digits)


def item_contribution(order, value):
    """order — fikr raqami (1–10), value — javob (1–5)."""
    return value - 1 if order % 2 else 5 - value


def score(values):
    """values — {fikr raqami: javob 1–5}. To'liq bo'lmasa None."""
    if any(values.get(order) is None for order in range(1, ITEMS + 1)):
        return None
    return 2.5 * sum(item_contribution(order, values[order]) for order in range(1, ITEMS + 1))


def grade(value):
    return next(label for bound, label in GRADES if value >= bound)


def acceptability(value):
    return next(label for bound, label in ACCEPTABILITY if value >= bound)


def responses(quiz, students=None):
    """{talaba id: {fikr raqami: javob}} — faqat topshirilgan urinishlar."""
    questions = list(quiz.questions.prefetch_related("choices").order_by("order"))
    attempts = QuizAttempt.objects.filter(quiz=quiz)
    if students is not None:
        attempts = attempts.filter(student__in=students)
    result = {}
    for attempt in attempts:
        attempt = finalize_if_expired(attempt)
        if not attempt.submitted_at:
            continue
        result[attempt.student_id] = {
            question.order: likert_value(question, attempt.answers.get(str(question.pk), [])) for question in questions
        }
    return result


def summarize(scores, contributions=()):
    """scores — talabalar SUS ballari; contributions — har bir talaba uchun 10 ta to'g'rilangan qiymat (α uchun)."""
    stats = describe(scores)
    result = {"n": stats["n"], "mean": _r(stats["mean"]), "sd": _r(stats["sd"]), "median": None, "ci95": None,
              "min": _r(min(scores)) if scores else None, "max": _r(max(scores)) if scores else None,
              "grade": None, "acceptability": None, "benchmark": None, "alpha": None}
    if not scores:
        return result
    ordered = sorted(scores)
    middle = len(ordered) // 2
    result["median"] = _r(ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2)
    result["grade"], result["acceptability"] = grade(stats["mean"]), acceptability(stats["mean"])
    if stats["sd"]:
        se = stats["sd"] / math.sqrt(stats["n"])
        half = _t_ppf(0.975, stats["n"] - 1) * se
        result["ci95"] = [_r(stats["mean"] - half), _r(stats["mean"] + half)]
        t = (stats["mean"] - BENCHMARK) / se
        result["benchmark"] = {"value": BENCHMARK, "t": _r(t, 3), "df": stats["n"] - 1,
                               "p": _r(t_two_sided_p(t, stats["n"] - 1), 4)}
    alpha = cronbach_alpha(list(contributions)) if len(contributions) >= 2 else None
    result["alpha"] = _r(alpha, 3)
    return result


def report(quiz, students=None):
    data = responses(quiz, students)
    scores, contributions, incomplete = {}, [], 0
    for student_id, values in data.items():
        value = score(values)
        if value is None:
            incomplete += 1
            continue
        scores[student_id] = value
        contributions.append([item_contribution(order, values[order]) for order in range(1, ITEMS + 1)])
    items = []
    for order in range(1, ITEMS + 1):
        answers = [values[order] for values in data.values() if values.get(order) is not None]
        stats = describe(answers)
        items.append({"order": order, "positive": bool(order % 2), "text": SUS_ITEMS[order - 1],
                      "n": stats["n"], "mean": _r(stats["mean"]), "sd": _r(stats["sd"])})
    return {
        "quiz": {"id": quiz.pk, "title": quiz.title},
        "submitted": len(data),
        "incomplete": incomplete,
        "summary": summarize(list(scores.values()), contributions),
        "items": items,
        "scores": scores,
    }


def is_sus(quiz):
    return quiz.title == SUS_TITLE and quiz.questions.count() == ITEMS
