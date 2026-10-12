from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from grading.models import Grade
from learning.models import Assignment
from submissions.models import Submission

from . import services
from .models import Notification


@receiver(m2m_changed, sender=Assignment.groups.through)
def on_assignment_groups_added(sender, instance, action, reverse, pk_set, **kwargs):
    # Topshiriq guruhga berilganda (yaratishda yoki keyin guruh qo'shilganda)
    if action == "post_add" and not reverse and pk_set:
        services.notify_new_assignment(instance, pk_set)


@receiver(post_save, sender=Submission)
def on_submission_created(sender, instance, created, **kwargs):
    if created:
        services.notify_user(
            instance.assignment.author, Notification.Kind.NEW_SUBMISSION, instance.assignment
        )


@receiver(post_save, sender=Grade)
def on_grade_created(sender, instance, created, **kwargs):
    # Faqat birinchi marta baho qo'yilganda; baho o'zgartirilganda qayta xabar bormaydi
    if created:
        services.notify_user(
            instance.submission.student, Notification.Kind.GRADED, instance.submission.assignment
        )
