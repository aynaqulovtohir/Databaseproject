"""AI tahlili va chat-yordamchi modellari."""
from django.conf import settings
from django.db import models


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
