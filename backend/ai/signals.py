from django.db.models.signals import post_save
from django.dispatch import receiver

from submissions.models import Submission

from .models import AIAnalysis


@receiver(post_save, sender=Submission)
def queue_analysis_for_new_submission(sender, instance, created, **kwargs):
    # Har bir yangi urinish avtomatik tahlil navbatiga qo'yiladi
    if created:
        AIAnalysis.objects.create(submission=instance)
