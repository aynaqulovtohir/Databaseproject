"""Bildirishnomalarni navbatga qo'yish.

MUHIM (maxfiylik): xabar matnida faqat topshiriq sarlavhasi va muddat bo'ladi.
Ism, ball va izoh matni Telegram'ga yuborilmaydi.
"""
from datetime import timedelta

from django.utils import timezone

from users.models import User

from . import telegram
from .models import Notification

MAX_TITLE_LENGTH = 100
REMINDER_WINDOW = timedelta(hours=24)
RISK_DIGEST_INTERVAL = timedelta(days=7)


def short_title(assignment):
    title = assignment.title
    return title if len(title) <= MAX_TITLE_LENGTH else title[: MAX_TITLE_LENGTH - 1] + "…"


def format_deadline(assignment):
    return timezone.localtime(assignment.deadline).strftime("%d.%m.%Y %H:%M")


def build_text(kind, assignment):
    title = short_title(assignment)
    if kind == Notification.Kind.NEW_ASSIGNMENT:
        return f"Yangi topshiriq: «{title}». Muddat: {format_deadline(assignment)}."
    if kind == Notification.Kind.GRADED:
        return f"«{title}» topshirig'i baholandi. Natijani platformada ko'ring."
    if kind == Notification.Kind.RETURNED:
        return f"«{title}» topshirig'i qayta ishlashga qaytarildi. Izohni platformada ko'ring."
    if kind == Notification.Kind.DEADLINE_REMINDER:
        return f"«{title}» topshirig'i muddati tugashiga 24 soatdan kam qoldi."
    if kind == Notification.Kind.NEW_SUBMISSION:
        return f"«{title}» topshirig'iga yangi yechim keldi."
    raise ValueError(f"Noma'lum bildirishnoma turi: {kind}")


def reachable(users):
    """Faqat faol va Telegram'ni bog'lagan foydalanuvchilar."""
    return users.filter(is_active=True, telegram_account__isnull=False)


def notify(users, kind, assignment):
    """Berilgan foydalanuvchilar uchun xabarlarni navbatga qo'yadi."""
    if not telegram.is_configured():
        return 0
    text = build_text(kind, assignment)
    notifications = [
        Notification(user=user, assignment=assignment, kind=kind, text=text) for user in reachable(users)
    ]
    # ignore_conflicts: takroriy eslatma yaratilmaydi
    Notification.objects.bulk_create(notifications, ignore_conflicts=True)
    return len(notifications)


def notify_user(user, kind, assignment):
    return notify(User.objects.filter(pk=user.pk), kind, assignment)


def notify_new_assignment(assignment, group_ids):
    students = User.objects.filter(role=User.Role.STUDENT, group_id__in=group_ids)
    return notify(students, Notification.Kind.NEW_ASSIGNMENT, assignment)


def notify_returned(submission):
    return notify_user(submission.student, Notification.Kind.RETURNED, submission.assignment)


def create_risk_digests():
    """O'qituvchilarga haftasiga bir marta: o'z guruhlarida yuqori xavfli talabalar bo'lsa, qisqa xulosa."""
    from labs.risk import digest_text

    if not telegram.is_configured():
        return 0
    week_ago = timezone.now() - RISK_DIGEST_INTERVAL
    created = 0
    teachers = reachable(User.objects.filter(role=User.Role.TEACHER)).exclude(
        notifications__kind=Notification.Kind.RISK_DIGEST, notifications__created_at__gte=week_ago
    )
    for teacher in teachers.distinct():
        text = digest_text(teacher.teaching_groups.order_by("name"))
        if text:
            Notification.objects.create(user=teacher, kind=Notification.Kind.RISK_DIGEST, text=text)
            created += 1
    return created


def create_deadline_reminders():
    """Muddati 24 soat ichida tugaydigan topshiriqlar uchun, hali topshirmagan talabalarga eslatma."""
    from learning.models import Assignment

    if not telegram.is_configured():
        return 0
    now = timezone.now()
    created = 0
    for assignment in Assignment.objects.filter(deadline__gt=now, deadline__lte=now + REMINDER_WINDOW):
        students = (
            User.objects.filter(role=User.Role.STUDENT, group__in=assignment.groups.all())
            .exclude(submissions__assignment=assignment)
            .exclude(
                notifications__assignment=assignment,
                notifications__kind=Notification.Kind.DEADLINE_REMINDER,
            )
            .distinct()
        )
        created += notify(students, Notification.Kind.DEADLINE_REMINDER, assignment)
    return created
