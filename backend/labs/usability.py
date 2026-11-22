"""Foydalanish sinovi hisoboti (docs/foydalanish-sinovi.md): T1–T7 topshiriqlari, log to'liqligi va AI ishlatilishi.

Loglardan olinadigan qiymatlar: 2 — bajarilgan, 0 — bajarilmagan. "Yordam bilan" (1) faqat kuzatuv varag'idan
ma'lum, shuning uchun kuzatuvchi jadvalni qo'lda tuzatadi. Topshiriqlar:
T1 — rozilik qarori berilgan (platformaga kirgan);
T2 — o'quv laboratoriyasidagi oxirgi diagrammada kamida 3 obyekt va 2 bog'lanish;
T3 — kamida bitta tekshiruv va undan keyin diagramma o'zgargan;
T4 — o'quv laboratoriyasida AI maslahati yoki murabbiy savoli. Muvaffaqiyatli javob yo'q, lekin AI xizmati xato
     bergan urinish (AIFailure) bor bo'lsa — talaba aybi emas: T4 baholanmaydi (None, "E" belgisi), mezon ulushidan
     chiqariladi va soni alohida ko'rsatiladi;
T5 — o'quv laboratoriyasi baholashga topshirilgan;
T6 — imtihon (AI'siz) topshirig'i topshirilgan;
T7 — SUS so'rovnomasining 10 ta fikriga ham javob berilgan (SUS berilmasa — hisoblanmaydi).

Log to'liqligi ikki ta'rifda: (a) kamida MIN_SNAPSHOTS oraliq holat; (b) jarayon tiklanadi — kamida bitta oraliq
holat bor va topshirishdan oldingi oxirgi holat topshirilgan diagrammaga teng. O'quv (T2–T5) va imtihon (T6, AI'siz)
ishlari alohida hisoblanadi: oldindan belgilangan mezon (≥ 90%) faqat imtihon ishlariga, (b) ta'rif bo'yicha.
"""
from collections import Counter

from quizzes.services import likert_value

from .models import AIFailure, ErSnapshot, LabAttempt, LabChatMessage, LabGrade

TASKS = ("T1", "T2", "T3", "T4", "T5", "T6", "T7")
MIN_SNAPSHOTS = 5
MIN_ENTITIES, MIN_RELATIONSHIPS = 3, 2


def _snapshots(student, lab):
    return list(ErSnapshot.objects.filter(student=student, lab=lab).order_by("created_at", "id"))


def _log_complete(snapshots, submission):
    """(a) holatlar soni yetarli, (b) jarayon topshirilgan diagrammagacha tiklanadi."""
    enough = len(snapshots) >= MIN_SNAPSHOTS
    if submission is None or not snapshots:
        return enough, False
    before = [s for s in snapshots if s.created_at <= submission.created_at]
    return enough, bool(before) and before[-1].diagram == submission.diagram


def _sus_answers(quiz, student):
    attempt = quiz.attempts.filter(student=student, submitted_at__isnull=False).first()
    if attempt is None:
        return 0
    return sum(likert_value(q, attempt.answers.get(str(q.pk), [])) is not None for q in quiz.questions.all())


def student_row(student, learn, exam, sus=None):
    snaps = _snapshots(student, learn)
    exam_snaps = _snapshots(student, exam)
    attempts = list(LabAttempt.objects.filter(student=student, lab=learn).order_by("created_at", "id"))
    checks = [a for a in attempts if not a.is_submission]
    submission = next((a for a in attempts if a.is_submission), None)
    exam_submission = LabAttempt.objects.filter(student=student, lab=exam, is_submission=True).order_by("created_at", "id").first()
    last = snaps[-1].diagram if snaps else {"entities": [], "relationships": []}
    hints = sum(len(a.ai_hints or []) for a in attempts)
    questions = LabChatMessage.objects.filter(student=student, lab=learn, role=LabChatMessage.Role.USER).count()
    ai_failed = AIFailure.objects.filter(student=student, lab=learn).count()
    grade = LabGrade.objects.filter(student=student, lab=learn).first()
    tasks = {
        "T1": student.research_consent is not None,
        "T2": len(last.get("entities", [])) >= MIN_ENTITIES and len(last.get("relationships", [])) >= MIN_RELATIONSHIPS,
        "T3": bool(checks) and any(s.created_at > checks[0].created_at and s.diagram != checks[0].diagram for s in snaps),
        "T4": True if hints + questions > 0 else None if ai_failed else False,
        "T5": grade is not None,
        "T6": LabGrade.objects.filter(student=student, lab=exam).exists(),
        "T7": None if sus is None else _sus_answers(sus, student) == sus.questions.count(),
    }
    minutes = None
    if submission and snaps:
        minutes = round((submission.created_at - snaps[0].created_at).total_seconds() / 60, 1)
    return {
        "student": student,
        "tasks": {key: (None if value is None else 2 if value else 0) for key, value in tasks.items()},
        "snapshots": (len(snaps), len(exam_snaps)),
        "logs": [_log_complete(snaps, submission), _log_complete(exam_snaps, exam_submission)],
        "hints": hints,
        "ai_failed": ai_failed,
        "t4_ai_error": hints + questions == 0 and ai_failed > 0,
        "coach_questions": questions,
        "grade_source": grade.source if grade else None,
        "learn_minutes": minutes,
    }


def report(students, learn, exam, sus=None):
    rows = [student_row(student, learn, exam, sus) for student in students]
    n = len(rows)
    summary = {}
    for task in TASKS:
        values = [row["tasks"][task] for row in rows if row["tasks"][task] is not None]
        summary[task] = {"done": sum(v == 2 for v in values), "n": len(values)}

    def log_stats(index):
        works = [row["logs"][index] for row in rows if row["snapshots"][index]]
        return {"works": len(works), "enough_snapshots": sum(log[0] for log in works),
                "reconstructed": sum(log[1] for log in works), "min_snapshots": MIN_SNAPSHOTS}

    return {
        "students": n,
        "rows": rows,
        "tasks": summary,
        "t4_ai_errors": sum(row["t4_ai_error"] for row in rows),
        "logs": {"learn": log_stats(0), "exam": log_stats(1)},
        "ai": {
            "hints": sum(row["hints"] for row in rows),
            "coach_questions": sum(row["coach_questions"] for row in rows),
            "users": sum(row["hints"] + row["coach_questions"] > 0 for row in rows),
            "failed_requests": sum(row["ai_failed"] for row in rows),
        },
        "grade_sources": dict(Counter(row["grade_source"] for row in rows if row["grade_source"])),
    }
