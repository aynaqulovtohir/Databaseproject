"""O'qituvchi qo'ygan yakuniy baho."""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

MAX_SCORE = 100


class Grade(models.Model):
    submission = models.OneToOneField(
        "submissions.Submission",
        verbose_name="yechim",
        on_delete=models.CASCADE,
        related_name="grade",
    )
    score = models.PositiveSmallIntegerField(
        "ball", validators=[MinValueValidator(0), MaxValueValidator(MAX_SCORE)]
    )
    # Rubrika bo'yicha baholanganda: [{"name", "points", "score"}] (o'sha paytdagi mezonlar nusxasi); score — yig'indi
    rubric_scores = models.JSONField("mezonlar bo'yicha ballar", null=True, blank=True)
    # Bosqich bahosi bosqich mezonlari ballari yig'indisidan oshmaydi; bosqichsiz topshiriqda 100
    max_score = models.PositiveSmallIntegerField("eng yuqori ball", default=MAX_SCORE)
    comment = models.TextField("izoh", blank=True)
    # Baho qo'yilgan paytdagi AI taklifi (statistika uchun; talabaga ko'rinmaydi)
    ai_suggested_score = models.PositiveSmallIntegerField("AI taklif qilgan ball", null=True, blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="baholagan",
        null=True,
        on_delete=models.SET_NULL,
        related_name="given_grades",
    )
    graded_at = models.DateTimeField("baholangan vaqti", auto_now_add=True)
    updated_at = models.DateTimeField("o'zgartirilgan vaqti", auto_now=True)

    class Meta:
        verbose_name = "baho"
        verbose_name_plural = "baholar"
        ordering = ["-graded_at"]

    def __str__(self):
        return f"{self.submission}: {self.score}"
