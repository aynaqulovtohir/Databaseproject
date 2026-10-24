"""Test va so'rovnomaning psixometrik tahlili (klassik test nazariyasi).

Test (kirish, chiqish, kechiktirilgan, oddiy):
- ishonchlilik: KR-20 (hamma savol bitta to'g'ri javobli — 0/1 ball) yoki Cronbach α (qisman ball bor), SEM;
- har bir savol: qiyinlik p (o'rtacha ball ulushi), tuzatilgan "savol — qolgan savollar" korrelyatsiyasi r,
  yuqori/quyi 27% indeksi D, "olib tashlansa α";
- variantlar (distraktorlar) tahlili: har bir variantni tanlaganlar ulushi — hammasi, yuqori va quyi guruhda.
  Ishlamaydigan (deyarli hech kim tanlamagan) va kuchli talabalarni chalg'itadigan variantlar belgilanadi.
So'rovnoma (Likert): Cronbach α (hamma savolga javob berganlar), har bir fikr uchun tuzatilgan r va "olib tashlansa α".

Faqat topshirgan va tadqiqotga rozi bo'lgan talabalar (users/consent.py). Kamida MIN_STUDENTS ta topshirish kerak.
"""
from collections import defaultdict

from labs.psychometrics import (
    ALPHA_GAIN,
    ALPHA_LEVELS,
    DISCRIMINATION,
    EXTREME_SHARE,
    MIN_EXTREME,
    RELIABLE_STUDENTS,
    VERDICTS,
    _label,
    _mean,
    _round,
    _variance,
    cronbach_alpha,
    pearson,
)
from users.consent import consent_required, participant_ids

from .models import Question, Quiz, QuizAttempt
from .services import finalize_if_expired, likert_value
from .survey_bank import EXTERNAL_AI_TEXTS

MIN_STUDENTS = 5
# Variantni shundan kam talaba tanlasa, u "ishlamaydi" (javobni topishga xalaqit bermaydi)
DEAD_DISTRACTOR = 0.05
# Savol qiyinligi: bundan oson yoki qiyin savollar talabalarni yaxshi ajratmaydi
TOO_EASY, TOO_HARD = 0.90, 0.20


def _attempts(quiz):
    allowed = participant_ids()
    attempts = [
        finalize_if_expired(attempt)
        for attempt in QuizAttempt.objects.filter(quiz=quiz).select_related("quiz", "student")
    ]
    submitted = [attempt for attempt in attempts if attempt.submitted_at]
    included = [attempt for attempt in submitted if allowed is None or attempt.student_id in allowed]
    return sorted(included, key=lambda attempt: attempt.pk), len(submitted) - len(included)


def _reliability(matrix):
    alpha = cronbach_alpha(matrix) if len(matrix) >= MIN_STUDENTS else None
    totals = [sum(row) for row in matrix]
    variance = _variance(totals)
    sd = variance**0.5 if variance else None
    return alpha, totals, sd


def analyse_quiz(quiz):
    if quiz.kind == Quiz.Kind.SURVEY:
        return analyse_survey(quiz)
    questions = list(quiz.questions.prefetch_related("choices"))
    attempts, excluded = _attempts(quiz)
    base = {
        "kind": "test",
        "consent_required": consent_required(),
        "students": len(attempts),
        "excluded_no_consent": excluded,
        "min_students": MIN_STUDENTS,
        "reliable_students": RELIABLE_STUDENTS,
    }
    if len(attempts) < MIN_STUDENTS or len(questions) < 2:
        return {**base, "enough": False, "reliability": None, "questions": []}

    matrix = [[float(attempt.results.get(str(question.pk), 0)) for question in questions] for attempt in attempts]
    alpha, totals, sd = _reliability(matrix)
    max_total = sum(question.points for question in questions)
    dichotomous = all(question.kind == Question.Kind.SINGLE for question in questions)

    # Yuqori va quyi guruhlar: umumiy ball bo'yicha 27% (har birida kamida 3 talaba)
    size = round(EXTREME_SHARE * len(attempts))
    ranked = sorted(range(len(attempts)), key=lambda index: totals[index])
    upper, lower = (set(ranked[-size:]), set(ranked[:size])) if size >= MIN_EXTREME else (set(), set())

    rows = []
    for index, question in enumerate(questions):
        scores = [row[index] for row in matrix]
        rest = [total - score for total, score in zip(totals, scores)]
        p = _mean(scores) / question.points if question.points else None
        r = pearson(scores, rest)
        d = None
        if upper:
            d = (_mean(scores[i] for i in upper) - _mean(scores[i] for i in lower)) / question.points
        without = cronbach_alpha([row[:index] + row[index + 1 :] for row in matrix]) if len(questions) > 2 else None
        if without is not None and alpha is None:
            without = None

        choices = []
        selected = [set(attempts[i].answers.get(str(question.pk), [])) for i in range(len(attempts))]
        for choice in question.choices.all():
            share = lambda ids: _round(sum(1 for i in ids if choice.pk in selected[i]) / len(ids)) if ids else None  # noqa: E731
            item = {
                "id": choice.pk,
                "text": choice.text,
                "is_correct": choice.is_correct,
                "share": share(range(len(attempts))),
                "upper": share(upper),
                "lower": share(lower),
                "flag": None,
            }
            if choice.is_correct:
                if upper and item["upper"] < item["lower"]:
                    item["flag"] = "Kuchli talabalar bu to'g'ri javobni kamroq tanlagan: kalitni tekshiring."
            elif item["share"] is not None and item["share"] < DEAD_DISTRACTOR:
                item["flag"] = "Deyarli hech kim tanlamagan: ishonarliroq noto'g'ri variant bilan almashtiring."
            elif upper and item["upper"] > item["lower"]:
                item["flag"] = "Kuchli talabalarni chalg'itadi: savol yoki variant matni noaniq bo'lishi mumkin."
            choices.append(item)
        skipped = sum(1 for chosen in selected if not chosen) / len(attempts)

        advice = []
        if p is not None and p > TOO_EASY:
            advice.append("Juda oson: deyarli hamma to'g'ri javob bergan, talabalarni ajratmaydi.")
        elif p is not None and p < TOO_HARD:
            advice.append("Juda qiyin: savol matni, to'g'ri javob yoki mavzu dars o'tilganini tekshiring.")
        if r is not None and r < 0:
            advice.append("Kuchli talabalar bu savolga kuchsizlardan yomonroq javob bergan: kalit xato bo'lishi mumkin.")
        elif r is not None and r < 0.20:
            advice.append("Talabalarni bilim darajasi bo'yicha yaxshi ajratmaydi.")
        if without is not None and without > alpha + ALPHA_GAIN:
            advice.append("Olib tashlansa, testning ishonchliligi oshadi.")
        if any(choice["flag"] for choice in choices):
            advice.append("Variantlarni ko'rib chiqing (pastdagi belgilar).")
        verdict = "replace" if (r is not None and r < 0) else ("review" if advice else "good")
        rows.append(
            {
                "id": question.pk,
                "order": question.order,
                "text": question.text,
                "kind": question.kind,
                "points": question.points,
                "p": _round(p),
                "r": _round(r),
                "discrimination": _label(DISCRIMINATION, r),
                "d": _round(d),
                "alpha_if_deleted": _round(without, 3),
                "skipped": _round(skipped),
                "choices": choices,
                "verdict": {"key": verdict, "label": VERDICTS[verdict]},
                "advice": advice,
            }
        )

    return {
        **base,
        "enough": True,
        "reliability": {
            "coefficient": "KR-20" if dichotomous else "Cronbach α",
            "alpha": _round(alpha, 3),
            "interpretation": _label(ALPHA_LEVELS, alpha),
            "questions": len(questions),
            "mean": _round(_mean(totals), 2),
            "sd": _round(sd, 2),
            "max": max_total,
            "sem": _round(sd * (1 - alpha) ** 0.5, 2) if sd and alpha is not None and alpha < 1 else None,
        },
        "extreme_groups": size if upper else 0,
        "questions": rows,
    }


def _scale(label, questions, attempts, answers):
    """Bir guruh fikrlar uchun α: shu fikrlarning hammasiga javob berganlar bo'yicha."""
    complete = [attempt for attempt in attempts if all(answers[attempt.pk].get(q.pk) is not None for q in questions)]
    matrix = [[answers[attempt.pk][q.pk] for q in questions] for attempt in complete]
    alpha = cronbach_alpha(matrix) if len(matrix) >= MIN_STUDENTS and len(questions) >= 2 else None
    items = []
    for index, question in enumerate(questions):
        values = [row[index] for row in matrix]
        rest = [sum(row) - row[index] for row in matrix]
        r = pearson(values, rest) if len(matrix) >= MIN_STUDENTS else None
        without = (
            cronbach_alpha([row[:index] + row[index + 1 :] for row in matrix]) if alpha is not None and len(questions) > 2 else None
        )
        advice = []
        if r is not None and r < 0.20:
            advice.append(
                "Qolgan fikrlar bilan bog'liqligi past: boshqa narsani o'lchayotgan yoki teskari ifodalangan bo'lishi mumkin."
            )
        if without is not None and without > alpha + ALPHA_GAIN:
            advice.append("Olib tashlansa, shkalaning ishonchliligi oshadi.")
        items.append(
            {
                "id": question.pk,
                "order": question.order,
                "text": question.text,
                "mean": _round(_mean(values)) if values else None,
                "r": _round(r),
                "alpha_if_deleted": _round(without, 3),
                "advice": advice,
            }
        )
    return {
        "label": label,
        "students": len(matrix),
        "alpha": _round(alpha, 3),
        "interpretation": _label(ALPHA_LEVELS, alpha),
        "items": items,
    }


def analyse_survey(quiz):
    # Tashqi AI haqidagi savollar fikr shkalasiga kirmaydi: ular foydalanish chastotasini o'lchaydi
    questions = [
        question
        for question in quiz.questions.prefetch_related("choices")
        if question.kind == Question.Kind.LIKERT and question.text not in EXTERNAL_AI_TEXTS
    ]
    attempts, excluded = _attempts(quiz)
    answers = defaultdict(dict)
    for attempt in attempts:
        for question in questions:
            answers[attempt.pk][question.pk] = likert_value(question, attempt.answers.get(str(question.pk), []))
    base = {
        "kind": "survey",
        "consent_required": consent_required(),
        "students": len(attempts),
        "excluded_no_consent": excluded,
        "min_students": MIN_STUDENTS,
        "reliable_students": RELIABLE_STUDENTS,
    }
    if len(attempts) < MIN_STUDENTS or len(questions) < 2:
        return {**base, "enough": False, "scales": []}
    # Hamma javob bergan fikrlar (masalan, AI haqidagi fikrlar faqat tajriba guruhiga beriladi)
    answered = {q.pk: sum(1 for attempt in attempts if answers[attempt.pk][q.pk] is not None) for q in questions}
    common = [q for q in questions if answered[q.pk] == len(attempts)]
    scales = [_scale("Barcha fikrlar", questions, attempts, answers)]
    if common and len(common) < len(questions):
        scales.append(_scale("Hamma javob bergan fikrlar", common, attempts, answers))
        partial = [q for q in questions if q not in common]
        if len(partial) >= 2:
            scales.append(_scale("Qisman berilgan fikrlar (masalan, faqat AI guruhiga)", partial, attempts, answers))
    return {**base, "enough": True, "scales": scales}
