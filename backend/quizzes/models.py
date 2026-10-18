"""Testlar: kirish/chiqish va kechiktirilgan testlar, oddiy testlar (bitta yoki bir nechta to'g'ri javobli savollar)
va so'rovnomalar (Likert shkalasi, 1-5, ball qo'yilmaydi).

Tadqiqot uchun: bitta talaba testni bir marta topshiradi, vaqt serverda nazorat qilinadi,
talabalar boshlagandan keyin savollar o'zgartirilmaydi.
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

# Vaqt tugaganidan keyin ham tarmoq kechikishi uchun qabul qilinadigan qo'shimcha vaqt
GRACE_SECONDS = 30

# Likert savolining variantlari (tartib raqami — shkaladagi qiymat). Har bir Likert savoliga
# avtomatik qo'shiladi, shunda javoblar oddiy savollardagidek variant id'lari bilan saqlanadi.
LIKERT_SCALE = [
    "Mutlaqo qo'shilmayman",
    "Qo'shilmayman",
    "Betarafman",
    "Qo'shilaman",
    "To'liq qo'shilaman",
]


class Quiz(models.Model):
    class Kind(models.TextChoices):
        PRE = "pre", "Kirish testi"
        POST = "post", "Chiqish testi"
        # Kurs tugagandan bir necha hafta keyin o'sha savollar bilan: bilim qanchalik saqlanganini o'lchaydi
        DELAYED = "delayed", "Kechiktirilgan test"
        PRACTICE = "practice", "Oddiy test"
        SURVEY = "survey", "So'rovnoma"

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
        LIKERT = "likert", "Likert shkalasi (1-5)"

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


class ExpertPanel(models.Model):
    """Test yoki so'rovnomani ekspertlar baholashi (mazmun validligi: Lawshe CVR, CVI).

    Yaratilganda savollar nusxasi (items) saqlanadi: ekspertlar aniq bir versiyani baholaydi, test keyin
    tahrirlansa ham natija o'zgarmaydi (tuzatilgan versiya uchun yangi bosqich ochiladi). Hisob — quizzes/expert.py.
    """

    quiz = models.ForeignKey(
        Quiz, verbose_name="test", null=True, blank=True, on_delete=models.SET_NULL, related_name="expert_panels"
    )
    quiz_title = models.CharField("test nomi", max_length=200)
    title = models.CharField("nomi", max_length=200)
    # Ekspertga: vosita nimani o'lchaydi (masalan, "ma'lumotlar bazasini loyihalash bo'yicha bilim")
    construct = models.TextField("o'lchanadigan tushuncha", max_length=2000)
    instructions = models.TextField("ekspertga ko'rsatma", blank=True, max_length=3000)
    # [{"key": "1", "order": 1, "text": ..., "kind": ..., "choices": [{"text", "is_correct"}]}]
    items = models.JSONField("savollar nusxasi")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="muallif", on_delete=models.PROTECT, related_name="expert_panels"
    )
    closes_at = models.DateTimeField("baholash tugash vaqti", null=True, blank=True)
    created_at = models.DateTimeField("yaratilgan vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "ekspert baholashi"
        verbose_name_plural = "ekspert baholashlari"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title

    def is_open(self, now=None):
        return self.closes_at is None or (now or timezone.now()) < self.closes_at


class ExpertInvite(models.Model):
    """Bitta ekspertning shaxsiy havolasi va baholari. Havola tokeni bazada faqat xesh (SHA-256) ko'rinishida."""

    panel = models.ForeignKey(ExpertPanel, verbose_name="ekspert baholashi", on_delete=models.CASCADE, related_name="invites")
    # O'qituvchi uchun belgi (masalan, "1-ekspert, TATU"): ekspertning o'zi kiritgan ma'lumotdan alohida
    label = models.CharField("belgi", max_length=200)
    token_hash = models.CharField("havola xeshi", max_length=64, unique=True)
    revoked = models.BooleanField("bekor qilingan", default=False)
    # {"full_name", "degree", "position", "workplace", "experience_years"}
    expert = models.JSONField("ekspert haqida", default=dict, blank=True)
    # {"<item key>": {"essential": 1-3, "relevance": 1-4, "clarity": 1-4, "comment": str}}
    ratings = models.JSONField("baholar", default=dict, blank=True)
    created_at = models.DateTimeField("yaratilgan vaqti", auto_now_add=True)
    updated_at = models.DateTimeField("o'zgartirilgan vaqti", auto_now=True)
    submitted_at = models.DateTimeField("yuborilgan vaqti", null=True, blank=True)

    class Meta:
        verbose_name = "ekspert havolasi"
        verbose_name_plural = "ekspert havolalari"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.panel} / {self.label}"
