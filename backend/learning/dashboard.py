"""Bosh sahifa (boshqaruv paneli): rolga qarab qisqa ko'rsatkichlar, faollik grafigi, so'nggi harakatlar va eslatmalar.

Har bir ma'lumot mavjud ruxsat qoidalari orqali olinadi (visible_* funksiyalari): talaba faqat o'zini,
o'qituvchi faqat o'z topshiriq, laboratoriya va testlarini, admin hammasini ko'radi.
Javobda SQL kod, AI maslahati, javoblar va izoh matnlari bo'lmaydi — faqat sarlavha, vaqt va son.
"""
from datetime import datetime, time, timedelta

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from labs.access import visible_labs
from labs.models import LabAttempt
from quizzes.models import QuizAttempt
from quizzes.views import visible_quizzes
from submissions.access import visible_submissions
from submissions.models import Submission
from users.models import StudentGroup, User

from .access import visible_assignments
from config.i18n import tr

CHART_DAYS = 14
RECENT_LIMIT = 8
ALERT_LIMIT = 5
DEADLINE_WINDOW = timedelta(days=7)


def person(user):
    return user.get_full_name() or user.username


def scoped(user):
    """Foydalanuvchi ko'ra oladigan yechim, laboratoriya urinishi va test topshirishlari."""
    submissions = visible_submissions(user)
    if user.is_student:
        lab_attempts = LabAttempt.objects.filter(student=user)
        quiz_attempts = QuizAttempt.objects.filter(student=user)
    else:
        lab_attempts = LabAttempt.objects.filter(lab__in=visible_labs(user))
        quiz_attempts = QuizAttempt.objects.filter(quiz__in=visible_quizzes(user))
    return submissions, lab_attempts, quiz_attempts.filter(submitted_at__isnull=False)


def daily_counts(queryset, field, since):
    tz = timezone.get_current_timezone()
    rows = (
        queryset.filter(**{f"{field}__gte": since})
        .annotate(day=TruncDate(field, tzinfo=tz))
        .values("day")
        .annotate(n=Count("id"))
    )
    return {row["day"]: row["n"] for row in rows}


def activity_chart(submissions, lab_attempts, quiz_attempts):
    today = timezone.localdate()
    first = today - timedelta(days=CHART_DAYS - 1)
    since = timezone.make_aware(datetime.combine(first, time.min))
    series = {
        "submissions": daily_counts(submissions, "submitted_at", since),
        "lab_attempts": daily_counts(lab_attempts, "created_at", since),
        "quiz_attempts": daily_counts(quiz_attempts, "submitted_at", since),
    }
    days = [first + timedelta(days=i) for i in range(CHART_DAYS)]
    return {
        "days": [day.isoformat() for day in days],
        "series": {key: [counts.get(day, 0) for day in days] for key, counts in series.items()},
    }


def recent_activity(user, submissions, lab_attempts, quiz_attempts):
    staff = not user.is_student
    items = []
    for sub in submissions.order_by("-submitted_at", "-id")[:RECENT_LIMIT]:
        status = {
            Submission.Status.GRADED: "success",
            Submission.Status.RETURNED: "warning",
        }.get(sub.status, "primary")
        items.append(
            {
                "kind": "submission",
                "at": sub.submitted_at,
                "title": sub.assignment.title,
                "actor": person(sub.student) if staff else None,
                "status": sub.get_status_display(),
                "tone": status,
                "link": f"/submissions/{sub.pk}" if staff else f"/assignments/{sub.assignment_id}",
            }
        )
    for attempt in lab_attempts.select_related("lab", "student").order_by("-created_at", "-id")[:RECENT_LIMIT]:
        items.append(
            {
                "kind": "lab_attempt",
                "at": attempt.created_at,
                "title": attempt.lab.title,
                "actor": person(attempt.student) if staff else None,
                "status": tr("To'g'ri") if attempt.is_correct else tr("Xato"),
                "tone": "success" if attempt.is_correct else "danger",
                "link": f"/labs/{attempt.lab_id}",
            }
        )
    for attempt in quiz_attempts.select_related("quiz", "student").order_by("-submitted_at", "-id")[:RECENT_LIMIT]:
        percent = round(100 * attempt.score / attempt.max_score) if attempt.max_score else None
        items.append(
            {
                "kind": "quiz_attempt",
                "at": attempt.submitted_at,
                "title": attempt.quiz.title,
                "actor": person(attempt.student) if staff else None,
                "status": f"{percent}%" if percent is not None else tr("Topshirildi"),
                "tone": "info",
                "link": f"/quizzes/{attempt.quiz_id}",
            }
        )
    items.sort(key=lambda item: item["at"], reverse=True)
    return items[:RECENT_LIMIT]


def student_alerts(user):
    now = timezone.now()
    alerts = []
    submitted = set(Submission.objects.filter(student=user).values_list("assignment_id", flat=True))
    upcoming = (
        visible_assignments(user)
        .filter(deadline__gt=now, deadline__lte=now + DEADLINE_WINDOW)
        .exclude(pk__in=submitted)
        .order_by("deadline")[:ALERT_LIMIT]
    )
    for assignment in upcoming:
        alerts.append(
            {
                "tone": "warning",
                "title": assignment.title,
                "text": tr("Muddat yaqin, yechim hali topshirilmagan"),
                "at": assignment.deadline,
                "link": f"/assignments/{assignment.pk}",
            }
        )
    # Har bir topshiriq (va bosqich) bo'yicha oxirgi yechim qaytarilgan bo'lsa
    latest = {}
    for sub in Submission.objects.filter(student=user).select_related("assignment").order_by("submitted_at", "id"):
        latest[(sub.assignment_id, sub.stage_id)] = sub
    returned = [sub for sub in latest.values() if sub.status == Submission.Status.RETURNED]
    returned.sort(key=lambda sub: sub.submitted_at, reverse=True)
    for sub in returned[:ALERT_LIMIT]:
        alerts.append(
            {
                "tone": "danger",
                "title": sub.assignment.title,
                "text": tr("Qayta ishlashga qaytarilgan"),
                "at": sub.submitted_at,
                "link": f"/assignments/{sub.assignment_id}",
            }
        )
    return alerts


def staff_alerts(submissions):
    pending = submissions.filter(status=Submission.Status.SUBMITTED).order_by("submitted_at", "id")
    return [
        {
            "tone": "primary",
            "title": sub.assignment.title,
            "text": tr("Tekshirilmagan yechim: {student}", student=person(sub.student)),
            "at": sub.submitted_at,
            "link": f"/submissions/{sub.pk}",
        }
        for sub in pending[:ALERT_LIMIT]
    ]


def card(key, label, value, hint=""):
    return {"key": key, "label": label, "value": value, "hint": hint}


def student_cards(user, submissions, lab_attempts, quiz_attempts):
    assignments = visible_assignments(user)
    done = assignments.filter(submissions__student=user).distinct().count()
    total = assignments.count()
    labs_total = visible_labs(user).count()
    labs_solved = lab_attempts.filter(is_correct=True).values("lab_id").distinct().count()
    quizzes_total = visible_quizzes(user).exclude(kind="survey").count()
    quizzes_done = quiz_attempts.exclude(quiz__kind="survey").count()
    average = submissions.filter(grade__isnull=False).aggregate(avg=Avg("grade__score"))["avg"]
    return [
        card("assignments", tr("Topshiriqlar"), f"{done}/{total}", tr("topshirilgan")),
        card("labs", tr("Laboratoriyalar"), f"{labs_solved}/{labs_total}", tr("to'g'ri yechilgan")),
        card("quizzes", tr("Testlar"), f"{quizzes_done}/{quizzes_total}", tr("topshirilgan")),
        card("grade", tr("O'rtacha baho"), round(average, 1) if average is not None else "—", tr("baholangan ishlar bo'yicha")),
    ]


def teacher_cards(user, submissions, lab_attempts, quiz_attempts):
    week_ago = timezone.now() - timedelta(days=7)
    groups = StudentGroup.objects.filter(teachers=user)
    students = User.objects.filter(role=User.Role.STUDENT, is_active=True, group__in=groups).count()
    return [
        card("students", tr("Talabalar"), students, tr("{count} ta guruhda", count=groups.count())),
        card(
            "pending",
            tr("Tekshirilmagan yechimlar"),
            submissions.filter(status=Submission.Status.SUBMITTED).count(),
            tr("baholashni kutmoqda"),
        ),
        card("labs", tr("Laboratoriya urinishlari"), lab_attempts.filter(created_at__gte=week_ago).count(), tr("so'nggi 7 kunda")),
        card("quizzes", tr("Test topshirishlari"), quiz_attempts.filter(submitted_at__gte=week_ago).count(), tr("so'nggi 7 kunda")),
    ]


def admin_cards(submissions, lab_attempts):
    week_ago = timezone.now() - timedelta(days=7)
    users = User.objects.filter(is_active=True).aggregate(
        total=Count("id"),
        teachers=Count("id", filter=Q(role=User.Role.TEACHER)),
        students=Count("id", filter=Q(role=User.Role.STUDENT)),
    )
    return [
        card(
            "users",
            tr("Faol foydalanuvchilar"),
            users["total"],
            tr("{teachers} o'qituvchi, {students} talaba", teachers=users['teachers'], students=users['students']),
        ),
        card("groups", tr("Guruhlar"), StudentGroup.objects.count(), ""),
        card(
            "pending",
            tr("Tekshirilmagan yechimlar"),
            submissions.filter(status=Submission.Status.SUBMITTED).count(),
            tr("baholashni kutmoqda"),
        ),
        card("labs", tr("Laboratoriya urinishlari"), lab_attempts.filter(created_at__gte=week_ago).count(), tr("so'nggi 7 kunda")),
    ]


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        submissions, lab_attempts, quiz_attempts = scoped(user)
        if user.is_student:
            cards = student_cards(user, submissions, lab_attempts, quiz_attempts)
            alerts = student_alerts(user)
        elif user.is_teacher:
            cards = teacher_cards(user, submissions, lab_attempts, quiz_attempts)
            alerts = staff_alerts(submissions)
        else:
            cards = admin_cards(submissions, lab_attempts)
            alerts = staff_alerts(submissions)
        return Response(
            {
                "cards": cards,
                "chart": activity_chart(submissions, lab_attempts, quiz_attempts),
                "recent": recent_activity(user, submissions, lab_attempts, quiz_attempts),
                "alerts": alerts,
            }
        )
