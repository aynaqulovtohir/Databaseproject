"""Erta ogohlantirish: orqada qolayotgan talabalarni aniqlash (o'qituvchi uchun).

LLM ishlatilmaydi: har bir signal oddiy, tushuntirib beriladigan qoida. Signallarning vaznlari yig'indisidan
xavf darajasi chiqadi; o'qituvchiga daraja bilan birga sabablar ham ko'rsatiladi — qaror o'qituvchida.
Bu baho emas: faqat e'tibor kerak bo'lgan talabalarni oldinroq ko'rish uchun.
"""
from collections import defaultdict
from datetime import timedelta
from statistics import median

from django.utils import timezone

from quizzes.models import Quiz, QuizAttempt
from quizzes.services import percent
from users.models import User

from . import mastery
from .models import InterviewMessage, Lab, LabAttempt

INACTIVE_DAYS = 7
STUCK_ATTEMPTS = 8  # bitta laboratoriyada shuncha urinish va hali yechilmagan
LOW_MASTERY = 0.4
MIN_OBSERVATIONS = 3  # mavzu bo'yicha kamida shuncha kuzatuv bo'lsa, past o'zlashtirish signal bo'ladi
BEHIND_RATIO = 0.5  # yechgan laboratoriyalari guruh medianasining yarmidan kam
MIN_MEDIAN = 2
LOW_TEST = 40
HINT_LEVEL = 2  # shu darajadagi (yoki yuqori) AI maslahatlari
HINT_SHARE = 0.5
MIN_HINT_ATTEMPTS = 6

WEIGHTS = {"inactive": 2, "behind": 2, "stuck": 1, "low_mastery": 1, "low_test": 1, "hints": 1}
LEVELS = [(3, "high"), (2, "medium"), (1, "low")]
LEVEL_LABELS = {"high": "Yuqori", "medium": "O'rta", "low": "Past", "none": "Xavf yo'q"}


def level_of(score):
    return next((name for threshold, name in LEVELS if score >= threshold), "none")


def group_risk(group, now=None):
    """Guruh talabalari: xavf darajasi, sabablari va oxirgi faollik vaqti (yuqori xavfdan boshlab)."""
    now = now or timezone.now()
    students = list(User.objects.filter(role=User.Role.STUDENT, is_active=True, group=group).order_by("last_name", "first_name", "username"))
    ids = [student.pk for student in students]
    labs = mastery.course_order(Lab.objects.filter(groups=group))

    attempts = defaultdict(list)
    for attempt in LabAttempt.objects.filter(student_id__in=ids, lab__in=labs).only(
        "student_id", "lab_id", "is_correct", "ai_hint_level", "created_at"
    ).order_by("id"):
        attempts[attempt.student_id].append(attempt)
    # Oxirgi faollik: laboratoriya urinishi, test boshlash yoki buyurtmachi bilan suhbat
    last_activity = {}

    def seen(student_id, moment):
        if student_id not in last_activity or moment > last_activity[student_id]:
            last_activity[student_id] = moment

    for student_id, items in attempts.items():
        seen(student_id, items[-1].created_at)
    for quiz_attempt in QuizAttempt.objects.filter(student_id__in=ids).only("student_id", "started_at"):
        seen(quiz_attempt.student_id, quiz_attempt.started_at)
    for message in InterviewMessage.objects.filter(student_id__in=ids).only("student_id", "created_at"):
        seen(message.student_id, message.created_at)

    latest_test = {}
    for quiz_attempt in QuizAttempt.objects.filter(
        student_id__in=ids, submitted_at__isnull=False, quiz__kind__in=[Quiz.Kind.PRE, Quiz.Kind.POST, Quiz.Kind.DELAYED]
    ).order_by("submitted_at"):
        if quiz_attempt.max_score:
            latest_test[quiz_attempt.student_id] = percent(quiz_attempt)

    solved = {student.pk: {a.lab_id for a in attempts[student.pk] if a.is_correct} for student in students}
    group_median = median([len(items) for items in solved.values()]) if students else 0
    titles = {lab.pk: lab.title for lab in labs}

    rows = []
    for student in students:
        items = attempts[student.pk]
        reasons = []
        last = last_activity.get(student.pk)
        if labs and last is None:
            reasons.append(("inactive", "Hali hech qanday faollik yo'q (laboratoriya va test)."))
        elif last is not None and now - last >= timedelta(days=INACTIVE_DAYS):
            reasons.append(("inactive", f"{(now - last).days} kundan beri faol emas."))
        if group_median >= MIN_MEDIAN and len(solved[student.pk]) < BEHIND_RATIO * group_median:
            reasons.append(("behind", f"{len(solved[student.pk])} ta laboratoriya yechgan (guruh medianasi {group_median:g})."))
        by_lab = defaultdict(list)
        for attempt in items:
            by_lab[attempt.lab_id].append(attempt)
        stuck = [lab_id for lab_id, lab_attempts in by_lab.items() if len(lab_attempts) >= STUCK_ATTEMPTS and lab_id not in solved[student.pk]]
        if stuck:
            names = ", ".join(f"«{titles[lab_id]}»" for lab_id in stuck[:2])
            reasons.append(("stuck", f"{names} laboratoriyasida {STUCK_ATTEMPTS}+ urinish, hali yechilmagan."))
        topics = mastery.student_mastery(labs, items)
        weak = [mastery.TOPIC_LABELS[topic] for topic, state in topics.items() if state["observations"] >= MIN_OBSERVATIONS and state["mastery"] < LOW_MASTERY]
        if weak:
            reasons.append(("low_mastery", f"Past o'zlashtirish: {', '.join(weak[:3])}."))
        if student.pk in latest_test and latest_test[student.pk] < LOW_TEST:
            reasons.append(("low_test", f"Oxirgi test natijasi {latest_test[student.pk]:g}%."))
        if len(items) >= MIN_HINT_ATTEMPTS and sum(1 for a in items if a.ai_hint_level >= HINT_LEVEL) >= HINT_SHARE * len(items):
            reasons.append(("hints", "Urinishlarning yarmidan ko'pida chuqur AI maslahatiga tayangan."))
        score = sum(WEIGHTS[code] for code, _ in reasons)
        level = level_of(score)
        rows.append(
            {
                "id": student.pk,
                "name": student.get_full_name() or student.username,
                "level": level,
                "level_label": LEVEL_LABELS[level],
                "score": score,
                "reasons": [{"code": code, "text": text} for code, text in reasons],
                "last_activity": last,
                "solved": len(solved[student.pk]),
            }
        )
    rows.sort(key=lambda row: (-row["score"], row["name"]))
    return {
        "group": {"id": group.pk, "name": group.name},
        "labs": len(labs),
        "median_solved": group_median,
        "students": rows,
    }


def digest_text(groups):
    """O'qituvchi uchun haftalik xulosa (faqat yuqori xavfli talabalar) yoki None — xabar kerak emas."""
    parts = []
    for group in groups:
        report = group_risk(group)
        high = [row for row in report["students"] if row["level"] == "high"]
        if high:
            lines = [f"• {row['name']}: {' '.join(reason['text'] for reason in row['reasons'][:2])}" for row in high[:10]]
            parts.append(f"{group.name} — {len(high)} ta talaba:\n" + "\n".join(lines))
    if not parts:
        return None
    return "Erta ogohlantirish: e'tibor kerak bo'lgan talabalar\n\n" + "\n\n".join(parts)
