"""Test topshirish: javoblarni tekshirish, saqlash, ball hisoblash va talabaga ko'rsatiladigan ma'lumotlar."""
import random

from django.db import transaction
from django.utils import timezone

from .models import LIKERT_SCALE, Question, QuizAttempt

# So'rovnoma natijasi bundan kam javob bo'lsa ko'rsatilmaydi: aks holda o'qituvchi kim topshirganini
# bilgani uchun alohida talabaning javobini aniqlay oladi
MIN_SURVEY_RESPONSES = 3


class AnswersError(ValueError):
    """Javoblar noto'g'ri formatda yoki testga tegishli bo'lmagan variantlar yuborilgan."""


def clean_answers(quiz, raw):
    """{"savol_id": [variant id'lari]} ni tekshiradi; faqat shu testning savol va variantlari qabul qilinadi."""
    if not isinstance(raw, dict):
        raise AnswersError("Javoblar noto'g'ri formatda.")
    questions = {str(question.pk): question for question in quiz.questions.all()}
    cleaned = {}
    for key, selected in raw.items():
        question = questions.get(str(key))
        if question is None:
            raise AnswersError("Bu testda bunday savol yo'q.")
        if not isinstance(selected, list) or not all(isinstance(item, int) and not isinstance(item, bool) for item in selected):
            raise AnswersError("Javoblar noto'g'ri formatda.")
        allowed = {choice.pk for choice in question.choices.all()}
        selected = sorted(set(selected))
        if any(item not in allowed for item in selected):
            raise AnswersError("Savolda bunday javob varianti yo'q.")
        if question.kind in (Question.Kind.SINGLE, Question.Kind.LIKERT) and len(selected) > 1:
            raise AnswersError("Bu savolda faqat bitta javob tanlanadi.")
        cleaned[str(question.pk)] = selected
    return cleaned


def score_question(question, selected):
    """Bitta to'g'ri javobli: to'liq ball yoki 0. Bir nechta to'g'ri javobli: (to'g'ri − noto'g'ri tanlanganlar) /
    to'g'ri variantlar soni ulushida ball (manfiy bo'lmaydi), shunda hammasini belgilab qo'yish foyda bermaydi."""
    if question.kind == Question.Kind.LIKERT:
        return 0.0
    correct = {choice.pk for choice in question.choices.all() if choice.is_correct}
    chosen = set(selected)
    if question.kind == Question.Kind.SINGLE:
        return float(question.points) if chosen == correct else 0.0
    if not correct:
        return 0.0
    fraction = max(0, len(chosen & correct) - len(chosen - correct)) / len(correct)
    return round(question.points * fraction, 2)


def finalize(attempt):
    """Testni yakunlaydi va ballni hisoblaydi (ikki marta chaqirilsa ham bir marta bajariladi)."""
    with transaction.atomic():
        attempt = QuizAttempt.objects.select_for_update().get(pk=attempt.pk)
        if attempt.submitted_at:
            return attempt
        results, score, max_score = {}, 0.0, 0.0
        for question in attempt.quiz.questions.prefetch_related("choices"):
            earned = score_question(question, attempt.answers.get(str(question.pk), []))
            results[str(question.pk)] = earned
            score += earned
            max_score += question.points
        attempt.results = results
        attempt.score = round(score, 2)
        attempt.max_score = max_score
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=["results", "score", "max_score", "submitted_at"])
    return attempt


def finalize_if_expired(attempt):
    """Vaqti tugagan, lekin topshirilmagan testni yakunlaydi (talaba sahifani yopib ketgan bo'lsa ham)."""
    if attempt and not attempt.submitted_at and attempt.is_expired():
        return finalize(attempt)
    return attempt


def attempt_status(attempt):
    if attempt is None:
        return "not_started"
    return "submitted" if attempt.submitted_at else "in_progress"


def percent(attempt):
    return round(100 * attempt.score / attempt.max_score, 1) if attempt.max_score else 0.0


def taking_payload(attempt):
    """Talaba testni yechayotganda: savollar (to'g'ri javoblarsiz), saqlangan javoblar va vaqt chegarasi.

    Variantlar har bir talaba uchun boshqacha, lekin har safar bir xil tartibda aralashtiriladi.
    """
    questions = []
    for question in attempt.quiz.questions.prefetch_related("choices"):
        choices = [{"id": choice.pk, "text": choice.text} for choice in question.choices.all()]
        # Likert shkalasi tartibi o'zgarmaydi (1 dan 5 gacha)
        if question.kind != Question.Kind.LIKERT:
            random.Random(attempt.pk * 100_003 + question.pk).shuffle(choices)
        questions.append(
            {"id": question.pk, "text": question.text, "kind": question.kind, "points": question.points, "choices": choices}
        )
    return {
        "questions": questions,
        "answers": attempt.answers,
        "started_at": attempt.started_at,
        "deadline": attempt.deadline,
        "server_now": timezone.now(),
    }


def likert_value(question, selected):
    """Likert savoliga javob: shkaladagi qiymat (1-5) yoki None."""
    if not selected:
        return None
    order = {choice.pk: choice.order for choice in question.choices.all()}
    return order.get(selected[0])


def survey_summary(quiz):
    """So'rovnoma natijasi: har bir savol bo'yicha javoblar taqsimoti va o'rtacha qiymat —
    hamma topshirganlar, tajriba (AI yoqilgan) va nazorat guruhlari bo'yicha alohida.
    Alohida talabaning javobi ko'rsatilmaydi: talabalar ochiq javob berishlari uchun. Javoblari
    MIN_SURVEY_RESPONSES tadan kam bo'lgan qism yashiriladi (hidden). Tajriba/nazorat qismlaridan biri
    yashirilsa, ikkinchisi ham yashiriladi: aks holda "hammasi − boshqa qism" ayirmasi uni ochib qo'yadi."""
    attempts = [
        finalize_if_expired(attempt)
        for attempt in QuizAttempt.objects.filter(quiz=quiz).select_related("quiz", "student__group")
    ]
    attempts = [attempt for attempt in attempts if attempt.submitted_at]

    def empty():
        return {"count": 0, "mean": None, "distribution": [0] * 5}

    questions = []
    for question in quiz.questions.prefetch_related("choices"):
        segments = {"all": empty(), "ai": empty(), "control": empty()}
        for attempt in attempts:
            value = likert_value(question, attempt.answers.get(str(question.pk), []))
            if value is None:
                continue
            group = attempt.student.group
            names = ["all"] + ([("ai" if group.ai_enabled else "control")] if group else [])
            for name in names:
                segments[name]["count"] += 1
                segments[name]["distribution"][value - 1] += 1
        small = lambda segment: 0 < segment["count"] < MIN_SURVEY_RESPONSES  # noqa: E731
        hide = {"all"} if small(segments["all"]) else set()
        if small(segments["ai"]) or small(segments["control"]) or hide:
            hide |= {"ai", "control"}
        for name, segment in segments.items():
            segment["hidden"] = name in hide and segment["count"] > 0
            if segment["hidden"]:
                segment["distribution"] = None
            elif segment["count"]:
                total = sum(value * count for value, count in enumerate(segment["distribution"], start=1))
                segment["mean"] = round(total / segment["count"], 2)
        questions.append({"id": question.pk, "order": question.order, "text": question.text, **segments})
    return {
        "respondents": len(attempts),
        "min_responses": MIN_SURVEY_RESPONSES,
        "scale": LIKERT_SCALE,
        "questions": questions,
    }


def result_payload(attempt):
    """Topshirilgan test natijasi. To'g'ri javoblar faqat o'qituvchi ruxsat bergan bo'lsa qo'shiladi."""
    payload = {
        "score": attempt.score,
        "max_score": attempt.max_score,
        "percent": percent(attempt),
        "submitted_at": attempt.submitted_at,
        "questions": None,
    }
    if attempt.quiz.show_answers:
        payload["questions"] = [
            {
                "id": question.pk,
                "text": question.text,
                "kind": question.kind,
                "points": question.points,
                "earned": attempt.results.get(str(question.pk), 0),
                "choices": [
                    {
                        "id": choice.pk,
                        "text": choice.text,
                        "is_correct": choice.is_correct,
                        "selected": choice.pk in attempt.answers.get(str(question.pk), []),
                    }
                    for choice in question.choices.all()
                ],
            }
            for question in attempt.quiz.questions.prefetch_related("choices")
        ]
    return payload
