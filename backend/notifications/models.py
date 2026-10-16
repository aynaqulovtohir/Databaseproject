"""Telegram bog'lanishi va bildirishnomalar navbati."""
from django.conf import settings
from django.db import models


class TelegramAccount(models.Model):
    """Foydalanuvchi va Telegram chat bog'lanishi.

    Telegram'dan faqat chat raqami saqlanadi: ism, username va telefon saqlanmaydi.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="foydalanuvchi",
        on_delete=models.CASCADE,
        related_name="telegram_account",
    )
    chat_id = models.BigIntegerField("chat raqami", unique=True)
    linked_at = models.DateTimeField("bog'langan vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "Telegram bog'lanishi"
        verbose_name_plural = "Telegram bog'lanishlari"


class TelegramLinkCode(models.Model):
    """Hisobni bog'lash uchun bir martalik kod. Bazada kodning o'zi emas, hash'i saqlanadi."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="foydalanuvchi",
        on_delete=models.CASCADE,
        related_name="telegram_link_code",
    )
    code_hash = models.CharField("kod hash'i", max_length=64, unique=True)
    expires_at = models.DateTimeField("amal qilish muddati")

    class Meta:
        verbose_name = "Telegram bog'lash kodi"
        verbose_name_plural = "Telegram bog'lash kodlari"


class Notification(models.Model):
    class Kind(models.TextChoices):
        NEW_ASSIGNMENT = "new_assignment", "Yangi topshiriq"
        GRADED = "graded", "Ish baholandi"
        RETURNED = "returned", "Ish qaytarildi"
        DEADLINE_REMINDER = "deadline_reminder", "Muddat eslatmasi"
        NEW_SUBMISSION = "new_submission", "Yangi yechim"
        # O'qituvchiga haftalik: e'tibor kerak bo'lgan talabalar (labs/risk.py)
        RISK_DIGEST = "risk_digest", "Erta ogohlantirish"

    class Status(models.TextChoices):
        PENDING = "pending", "Navbatda"
        SENT = "sent", "Yuborilgan"
        FAILED = "failed", "Yuborilmadi"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="kimga",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    assignment = models.ForeignKey(
        "learning.Assignment",
        verbose_name="topshiriq",
        null=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField("turi", max_length=20, choices=Kind.choices)
    text = models.TextField("matn")
    status = models.CharField("holati", max_length=10, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField("urinishlar soni", default=0)
    error_message = models.CharField("xato", max_length=255, blank=True)
    created_at = models.DateTimeField("yaratilgan vaqti", auto_now_add=True)
    sent_at = models.DateTimeField("yuborilgan vaqti", null=True, blank=True)

    class Meta:
        verbose_name = "bildirishnoma"
        verbose_name_plural = "bildirishnomalar"
        ordering = ["created_at", "id"]
        constraints = [
            # Bitta talabaga bitta topshiriq uchun eslatma faqat bir marta yuboriladi
            models.UniqueConstraint(
                fields=["user", "assignment"],
                condition=models.Q(kind="deadline_reminder"),
                name="unique_deadline_reminder",
            )
        ]
