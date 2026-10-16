"""Talaba yechimi: har bir topshirish alohida urinish sifatida saqlanadi."""
from django.conf import settings
from django.db import models

MAX_SQL_CODE_LENGTH = 50_000


class Submission(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Topshirilgan"
        GRADED = "graded", "Baholangan"
        RETURNED = "returned", "Qayta ishlashga qaytarilgan"

    # Yechim kelgan topshiriqni o'chirib bo'lmaydi
    assignment = models.ForeignKey(
        "learning.Assignment",
        verbose_name="topshiriq",
        on_delete=models.PROTECT,
        related_name="submissions",
    )
    # Talaba o'chirilsa, uning yechimlari ham o'chadi
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="talaba",
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    # Bosqichli loyihada: qaysi bosqich uchun (bosqichsiz topshiriqda bo'sh)
    stage = models.ForeignKey(
        "learning.AssignmentStage",
        verbose_name="bosqich",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="submissions",
    )
    # ER-diagramma bosqichida sql_code bo'sh, diagram to'ldiriladi (labs/er.py formati)
    sql_code = models.TextField("SQL kod", max_length=MAX_SQL_CODE_LENGTH, blank=True)
    diagram = models.JSONField("ER-diagramma", null=True, blank=True)
    attempt_number = models.PositiveIntegerField("urinish raqami")
    is_late = models.BooleanField("kechikkan", default=False)
    status = models.CharField(
        "holati", max_length=10, choices=Status.choices, default=Status.SUBMITTED
    )
    # O'qituvchi qayta ishlashga qaytarganda yozgan izoh
    return_comment = models.TextField("qaytarish izohi", blank=True)
    submitted_at = models.DateTimeField("topshirilgan vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "yechim"
        verbose_name_plural = "yechimlar"
        ordering = ["-submitted_at", "-id"]
        constraints = [
            # Urinishlar har bir bosqich uchun alohida raqamlanadi; bosqichsiz topshiriqda stage = NULL
            models.UniqueConstraint(
                fields=["assignment", "stage", "student", "attempt_number"],
                name="unique_attempt_per_student_stage",
                nulls_distinct=False,
            )
        ]

    def __str__(self):
        return f"{self.assignment} / {self.student} / {self.attempt_number}-urinish"
