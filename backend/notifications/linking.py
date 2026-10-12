"""Hisobni Telegram'ga bog'lash uchun bir martalik kodlar."""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import TelegramAccount, TelegramLinkCode

LINK_CODE_LIFETIME = timedelta(minutes=15)


def hash_code(code):
    return hashlib.sha256(code.encode()).hexdigest()


def create_link(user):
    """Yangi kod yaratadi (eskisi bekor bo'ladi). Qaytaradi: (havola, amal qilish muddati)."""
    code = secrets.token_urlsafe(24)
    expires_at = timezone.now() + LINK_CODE_LIFETIME
    TelegramLinkCode.objects.update_or_create(
        user=user, defaults={"code_hash": hash_code(code), "expires_at": expires_at}
    )
    return f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={code}", expires_at


def link_chat(code, chat_id):
    """Kod to'g'ri bo'lsa, chatni foydalanuvchiga bog'laydi. Qaytaradi: True/False."""
    with transaction.atomic():
        link_code = (
            TelegramLinkCode.objects.select_for_update()
            .select_related("user")
            .filter(code_hash=hash_code(code), expires_at__gt=timezone.now())
            .first()
        )
        if link_code is None or not link_code.user.is_active:
            return False
        # Bitta Telegram chat faqat bitta hisobga bog'lanadi
        TelegramAccount.objects.filter(chat_id=chat_id).exclude(user=link_code.user).delete()
        TelegramAccount.objects.update_or_create(user=link_code.user, defaults={"chat_id": chat_id})
        link_code.delete()
        return True


def unlink_user(user):
    TelegramLinkCode.objects.filter(user=user).delete()
    return TelegramAccount.objects.filter(user=user).delete()[0] > 0


def unlink_chat(chat_id):
    return TelegramAccount.objects.filter(chat_id=chat_id).delete()[0] > 0
