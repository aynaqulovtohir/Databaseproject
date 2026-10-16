"""Talabaning AI'dan kunlik foydalanish limiti.

Bosqichli maslahatlar (har bir daraja) va boshqa AI yordamlari (EXPLAIN tushuntirishi, murabbiy bilan suhbat,
yechimni tushuntirish, loyiha himoyasi) bitta umumiy kunlik limitdan (LAB_AI_DAILY_LIMIT) yechiladi:
yangi imkoniyat qo'shilgani uchun talaba AI'ni ko'proq ishlata olmaydi va xarajat oldindan ma'lum bo'ladi.
Baholash alohida limitga ega (LAB_AI_GRADES_DAILY_LIMIT).
"""
from datetime import datetime, time

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

import logging

from ai.client import AIError, AINotConfigured, AITransientError, is_configured

from .models import AIAction, LabAttempt

logger = logging.getLogger(__name__)


def _today_start():
    return timezone.make_aware(datetime.combine(timezone.localdate(), time.min))


def ai_advice_left(student):
    """Talaba bugun yana nechta AI yordami olishi mumkin (har bir maslahat darajasi alohida sanaladi)."""
    today_start = _today_start()
    hints = LabAttempt.objects.filter(student=student, ai_requested_at__gte=today_start).aggregate(
        total=Sum("ai_hint_level")
    )["total"]
    actions = AIAction.objects.filter(student=student, created_at__gte=today_start).count()
    return max(0, settings.LAB_AI_DAILY_LIMIT - (hints or 0) - actions)


def ai_grades_left(student):
    """Talaba bugun yana nechta topshirig'ini AI baholashi mumkin (undan keyin avtomatik baho)."""
    used = LabAttempt.objects.filter(student=student, is_submission=True, created_at__gte=_today_start()).count()
    # Hozirgina saqlangan urinishning o'zi ham hisobga kirgan
    return settings.LAB_AI_GRADES_DAILY_LIMIT - used + 1


def ai_usable(student):
    """AI shu talabaga ishlatiladimi: sozlangan va guruhida o'chirilmagan."""
    return is_configured() and student.ai_allowed


def refuse_ai(user):
    """AI yordami berib bo'lmasa — tayyor javob (403/503/429), aks holda None.

    Admin va o'qituvchi uchun kunlik limit yo'q (ular talaba emas), lekin AI sozlangan bo'lishi kerak.
    """
    if not user.ai_allowed:
        return Response({"detail": "Guruhingizda AI yordamchisi o'chirilgan."}, status=status.HTTP_403_FORBIDDEN)
    if not is_configured():
        return Response({"detail": "AI yordamchi hali sozlanmagan."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    if user.is_student and ai_advice_left(user) <= 0:
        return Response(
            {"detail": "Bugungi AI yordami limiti tugadi. Ertaga yana urinib ko'ring."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return None


def record_ai_action(user, kind):
    """Muvaffaqiyatli AI yordamini limitdan yechadi (faqat talaba uchun)."""
    if user.is_student:
        AIAction.objects.create(student=user, kind=kind)


def ai_error_response(exc, what="so'rov"):
    """AI xatosini talabaga tushunarli javobga aylantiradi."""
    if isinstance(exc, AINotConfigured):
        return Response({"detail": "AI yordamchi hali sozlanmagan."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    if isinstance(exc, AITransientError):
        return Response(
            {"detail": "AI vaqtincha ishlamayapti. Birozdan keyin qayta urinib ko'ring."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    logger.error("AI xatosi (%s): %s", what, exc)
    return Response({"detail": f"AI bu {what}ga javob bera olmadi."}, status=status.HTTP_502_BAD_GATEWAY)


SANDBOX_DOWN = "Laboratoriya bazasi vaqtincha ishlamayapti. Birozdan keyin qayta urinib ko'ring."


def sandbox_down_response():
    return Response({"detail": SANDBOX_DOWN}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
