"""Refresh tokenlarni bekor qilish.

- Har bir yangilanishda refresh token yangisiga almashtiriladi, eskisi ishlatilgan deb belgilanadi.
- Ishlatilgan token yana kelsa, uning nusxasi boshqa joyda (o'g'irlangan cookie) ishlatilmoqda deb hisoblanadi:
  foydalanuvchining barcha sessiyalari yopiladi. Istisno — almashtirilgandan keyin bir necha soniya ichida kelishi:
  bir vaqtda ochilgan ikki tab bir xil cookie bilan yangilaydi. Bunda faqat access token beriladi, cookie o'zgarmaydi.
- Chiqish (logout), parol almashtirish va bloklash tokenlarni darhol bekor qiladi.
- Bazada ro'yxatga olinmagan token (masalan, bu o'zgarishdan oldin berilgani) qabul qilinmaydi.

Sessiya muddati login vaqtidan hisoblanadi: yangi token eskisining tugash vaqtini meros oladi.
Access token (30 daqiqa) bekor qilinmaydi, u o'z muddati tugaguncha ishlaydi.
"""
import logging
from datetime import UTC, datetime, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenBackendError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.tokens import RefreshToken

from .models import IssuedRefreshToken

logger = logging.getLogger(__name__)

# Bir vaqtda yangilagan tablar uchun ruxsat etilgan oraliq
REUSE_GRACE = timedelta(seconds=30)


class RefreshFailed(Exception):
    """Token yaroqsiz, bekor qilingan yoki o'g'irlik belgisi bor: qayta login kerak."""


def _expires_at(token):
    return datetime.fromtimestamp(token["exp"], tz=UTC)


def _record(token, user):
    IssuedRefreshToken.objects.create(
        jti=token[api_settings.JTI_CLAIM], user=user, expires_at=_expires_at(token)
    )


def issue(user):
    """Login: yangi refresh token beradi va ro'yxatga oladi."""
    # Muddati o'tgan yozuvlar shu foydalanuvchi kirganda tozalanadi: jadval o'smaydi
    IssuedRefreshToken.objects.filter(user=user, expires_at__lt=timezone.now()).delete()
    token = RefreshToken.for_user(user)
    _record(token, user)
    return token


def _decode(raw):
    """Imzo, muddat va turini tekshiradi."""
    try:
        payload = token_backend.decode(raw, verify=True)
    except TokenBackendError:
        raise RefreshFailed
    if payload.get(api_settings.TOKEN_TYPE_CLAIM) != "refresh" or not payload.get(api_settings.JTI_CLAIM):
        raise RefreshFailed
    return payload


def rotate(raw):
    """Refresh: (access token, yangi refresh token yoki None) qaytaradi.

    None — bir vaqtda yangilagan tab: yangi cookie'ni boshqa so'rov allaqachon olgan.
    """
    payload = _decode(raw)
    now = timezone.now()
    with transaction.atomic():
        # Bir xil token bilan kelgan so'rovlar navbat bilan ishlanadi
        issued = (
            IssuedRefreshToken.objects.select_for_update()
            .select_related("user")
            .filter(jti=payload[api_settings.JTI_CLAIM])
            .first()
        )
        if issued is None or issued.revoked_at is not None or not issued.user.is_active:
            raise RefreshFailed
        user = issued.user

        if issued.used_at is None:
            issued.used_at = now
            issued.save(update_fields=["used_at"])
            new_token = RefreshToken.for_user(user)
            new_token.set_exp(from_time=_expires_at(payload), lifetime=timedelta(0))
            _record(new_token, user)
            return str(new_token.access_token), new_token
        if now - issued.used_at <= REUSE_GRACE:
            return str(RefreshToken.for_user(user).access_token), None
        # Istisno tranzaksiyani bekor qilmasligi uchun xato blokdan tashqarida ko'tariladi
        IssuedRefreshToken.objects.revoke_all(user)
    logger.warning("Ishlatilgan refresh token qayta keldi (foydalanuvchi id=%s): barcha sessiyalar yopildi", user.pk)
    raise RefreshFailed


def revoke(raw):
    """Chiqish: cookie'dagi tokenni bekor qiladi (yaroqsiz bo'lsa, hech narsa qilinmaydi)."""
    try:
        payload = _decode(raw)
    except RefreshFailed:
        return
    IssuedRefreshToken.objects.filter(
        jti=payload[api_settings.JTI_CLAIM], revoked_at__isnull=True
    ).update(revoked_at=timezone.now())
