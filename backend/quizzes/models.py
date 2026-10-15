"""Testlar: kirish/chiqish testlari va oddiy testlar (bitta yoki bir nechta to'g'ri javobli savollar).

Tadqiqot uchun: bitta talaba testni bir marta topshiradi, vaqt serverda nazorat qilinadi,
talabalar boshlagandan keyin savollar o'zgartirilmaydi.
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

# Vaqt tugaganidan keyin ham tarmoq kechikishi uchun qabul qilinadigan qo'shimcha vaqt
GRACE_SECONDS = 30


class Quiz(models.Model):
    class Kind(models.TextChoices):
        PRE = "pre", "Kirish testi"
        POST = "post", "Chiqish testi"
        PRACTICE = "practice", "Oddiy test"

    kind = models.CharField("turi", max_length=10, choices=Kind.choices, default=Kind.PRACTICE)
    title = models.CharField("sarlavha", max_length=200)
    description = models.TextField("izoh", blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="muallif", on_delete=models.PROTECT, related_name="quizzes"
    )
    groups = models.ManyToManyField("users.StudentGroup", verbose_name="guruhlar", related_name="quizzes")
    # Bo'sh bo'lsa — cheklovsiz
    opens_at = models.DateTimeField("ochilish vaqti", null=True, blank=True)
    closes_at = models.DateTimeField("yopilish vaqti", null=True, blank=True)
    time_limit_minutes = models.PositiveSmallIntegerField("vaqt chegarasi (daqiqa)", null=True, blank=True)
    # Topshirgandan keyin talabaga to'g'ri javoblar ko'rsatiladimi (kirish testida odatda yo'q)
    show_answers = models.BooleanField("to'g'ri javoblarni ko'rsatish", default=False)
    created_at = models.DateTimeField("yaratilgan vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "test"
        verbose_name_plural = "testlar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def is_open(self, now=None):
        now = now or timezone.now()
        return (self.opens_at is None or self.opens_at <= now) and (self.closes_at is None or now < self.closes_at)


class Question(models.Model):
    class Kind(models.TextChoices):
        SINGLE = "single", "Bitta to'g'ri javob"
        MULTIPLE = "multiple", "Bir nechta to'g'ri javob"

    quiz = models.ForeignKey(Quiz, verbose_name="test", on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveSmallIntegerField("tartib raqami")
    text = models.TextField("savol", max_length=2000)
    kind = models.CharField("turi", max_length=10, choices=Kind.choices, default=Kind.SINGLE)
    points = models.PositiveSmallIntegerField("ball", default=1)

    class Meta:
        verbose_name = "savol"
        verbose_name_plural = "savollar"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.quiz} / {self.order}"


class Choice(models.Model):
    question = models.ForeignKey(Question, verbose_name="savol", on_delete=models.CASCADE, related_name="choices")
    order = models.PositiveSmallIntegerField("tartib raqami")
    text = models.TextField("javob varianti", max_length=1000)
    is_correct = models.BooleanField("to'g'ri", default=False)

    class Meta:
        verbose_name = "javob varianti"
        verbose_name_plural = "javob variantlari"
        ordering = ["order", "id"]

    def __str__(self):
        return self.text[:50]


class QuizAttempt(models.Model):
    """Talabaning testni topshirishi (bitta test uchun bitta)."""

    quiz = models.ForeignKey(Quiz, verbose_name="test", on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="talaba", on_delete=models.CASCADE, related_name="quiz_attempts"
    )
    started_at = models.DateTimeField("boshlangan vaqti", auto_now_add=True)
    submitted_at = models.DateTimeField("topshirilgan vaqti", null=True, blank=True)
    # {"savol_id": [tanlangan variant id'lari]}
    answers = models.JSONField("javoblar", default=dict, blank=True)
    # {"savol_id": olingan ball} — topshirilganda hisoblanadi
    results = models.JSONField("savollar bo'yicha natija", default=dict, blank=True)
    score = models.FloatField("ball", default=0)
    max_score = models.FloatField("maksimal ball", default=0)

    class Meta:
        verbose_name = "test topshirish"
        verbose_name_plural = "test topshirishlar"
        constraints = [models.UniqueConstraint(fields=["quiz", "student"], name="unique_quiz_attempt_per_student")]

    def __str__(self):
        return f"{self.quiz} / {self.student}"

    @property
    def deadline(self):
        """Javoblar qabul qilinadigan oxirgi vaqt: vaqt chegarasi va test yopilishidan qaysi biri oldin."""
        limits = []
        if self.quiz.time_limit_minutes:
            limits.append(self.started_at + timedelta(minutes=self.quiz.time_limit_minutes))
        if self.quiz.closes_at:
            limits.append(self.quiz.closes_at)
        return min(limits) if limits else None

    def is_expired(self, now=None):
        deadline = self.deadline
        now = now or timezone.now()
        return deadline is not None and now > deadline + timedelta(seconds=GRACE_SECONDS)
