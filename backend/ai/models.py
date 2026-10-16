"""AI tahlili va chat-yordamchi modellari."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class AIAnalysis(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Navbatda"
        PROCESSING = "processing", "Tahlil qilinmoqda"
        DONE = "done", "Tayyor"
        FAILED = "failed", "Xato"

    submission = models.OneToOneField(
        "submissions.Submission",
        verbose_name="yechim",
        on_delete=models.CASCADE,
        related_name="analysis",
    )
    status = models.CharField("holati", max_length=10, choices=Status.choices, default=Status.PENDING)

    # Talabaga ko'rinadigan qism
    summary = models.TextField("umumiy xulosa", blank=True)
    issues = models.JSONField("topilgan muammolar", default=list, blank=True)
    recommendations = models.JSONField("tavsiyalar", default=list, blank=True)

    # Faqat o'qituvchi va adminga ko'rinadigan qism
    suggested_score = models.PositiveSmallIntegerField("taklif qilingan ball", null=True, blank=True)
    score_rationale = models.TextField("ball asosi", blank=True)
    error_message = models.TextField("xato matni", blank=True)

    # Texnik ma'lumot
    attempts = models.PositiveSmallIntegerField("urinishlar soni", default=0)
    model_name = models.CharField("AI modeli", max_length=100, blank=True)
    input_tokens = models.PositiveIntegerField("kirish tokenlari", default=0)
    output_tokens = models.PositiveIntegerField("chiqish tokenlari", default=0)
    created_at = models.DateTimeField("yaratilgan vaqti", auto_now_add=True)
    started_at = models.DateTimeField("boshlangan vaqti", null=True, blank=True)
    completed_at = models.DateTimeField("tugagan vaqti", null=True, blank=True)

    class Meta:
        verbose_name = "AI tahlili"
        verbose_name_plural = "AI tahlillari"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.submission} ({self.get_status_display()})"


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Talaba"
        ASSISTANT = "assistant", "AI"

    assignment = models.ForeignKey(
        "learning.Assignment",
        verbose_name="topshiriq",
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="talaba",
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    role = models.CharField("kim yozgan", max_length=10, choices=Role.choices)
    content = models.TextField("matn")
    created_at = models.DateTimeField("vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "chat xabari"
        verbose_name_plural = "chat xabarlari"
        ordering = ["created_at", "id"]


class AIUsage(models.Model):
    """Har bir AI so'rovining hisobi: xarajat va nosozliklarni kuzatish uchun.

    Kim so'raganligi va matn saqlanmaydi — faqat maqsad, model va token soni.
    """

    class Purpose(models.TextChoices):
        ANALYSIS = "analysis", "Topshiriq tahlili"
        CHAT = "chat", "Chat-yordamchi"
        LAB_ADVICE = "lab_advice", "SQL maslahati"
        LAB_GRADE = "lab_grade", "SQL baholash"
        ER_ADVICE = "er_advice", "ER maslahati"
        ER_GRADE = "er_grade", "ER baholash"
        PLAN_EXPLAIN = "plan_explain", "EXPLAIN tushuntirishi"
        PLAN_SUGGEST = "plan_suggest", "Indeks taklifi (tekshiriladi)"
        LAB_CHAT = "lab_chat", "Laboratoriya murabbiyi"
        SELF_EXPLAIN = "self_explain", "Yechimni tushuntirish"
        VIVA = "viva", "Loyiha himoyasi"
        VARIANT = "variant", "Topshiriq varianti"
        BUGGY_CODE = "buggy_code", "Xatoli kod yaratish"
        MISTAKES_SUMMARY = "mistakes_summary", "Xatolar xulosasi"
        OTHER = "other", "Boshqa"

    purpose = models.CharField("maqsad", max_length=20, choices=Purpose.choices, default=Purpose.OTHER)
    model_name = models.CharField("AI modeli", max_length=100, blank=True)
    input_tokens = models.PositiveIntegerField("kirish tokenlari", default=0)
    output_tokens = models.PositiveIntegerField("chiqish tokenlari", default=0)
    # Prompt caching: keshdan o'qilgan (arzon) va keshga yozilgan tokenlar; input_tokens — qolgan qismi
    cache_read_tokens = models.PositiveIntegerField("keshdan o'qilgan tokenlar", default=0)
    cache_write_tokens = models.PositiveIntegerField("keshga yozilgan tokenlar", default=0)
    # So'rov paytidagi narx bo'yicha hisoblangan xarajat (AQSh dollari). Eski yozuvlarda bo'sh — hisobotda
    # tokenlar joriy narx bo'yicha hisoblanadi
    cost = models.FloatField("narxi ($)", null=True, blank=True)
    ok = models.BooleanField("muvaffaqiyatli", default=True)
    error = models.CharField("xato", max_length=200, blank=True)
    created_at = models.DateTimeField("vaqti", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "AI so'rovi"
        verbose_name_plural = "AI so'rovlari"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_purpose_display()} / {self.model_name}: {self.input_tokens}+{self.output_tokens}"


class VivaSession(models.Model):
    """Loyiha himoyasi: AI talabaning O'Z yechimi bo'yicha savollar beradi, talaba javob yozadi, AI baholaydi.

    Maqsad — talaba yechimni tushunganini (va o'zi yozganini) tekshirish. Bahoga avtomatik ta'sir qilmaydi:
    tushunish darajasini o'qituvchi ko'radi va o'zi qaror qiladi.
    """

    class Status(models.TextChoices):
        ASKED = "asked", "Savollar berildi"
        EVALUATED = "evaluated", "Baholandi"

    submission = models.OneToOneField(
        "submissions.Submission", verbose_name="yechim", on_delete=models.CASCADE, related_name="viva"
    )
    status = models.CharField("holati", max_length=10, choices=Status.choices, default=Status.ASKED)
    questions = models.JSONField("savollar", default=list)
    answers = models.JSONField("javoblar", default=list, blank=True)
    # Talabaga ko'rinadi: har bir javob bo'yicha izoh
    feedback = models.JSONField("izohlar", default=list, blank=True)
    # Faqat o'qituvchi va adminga: tushunish darajasi (0-100) va xulosa
    understanding = models.PositiveSmallIntegerField("tushunish darajasi", null=True, blank=True)
    teacher_summary = models.TextField("o'qituvchi uchun xulosa", blank=True)
    created_at = models.DateTimeField("yaratilgan vaqti", auto_now_add=True)
    answered_at = models.DateTimeField("javob berilgan vaqti", null=True, blank=True)

    class Meta:
        verbose_name = "loyiha himoyasi"
        verbose_name_plural = "loyiha himoyalari"

    def __str__(self):
        return f"{self.submission} ({self.get_status_display()})"
