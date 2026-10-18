"""Talabaning ilmiy tadqiqotda ishtirok etishga roziligi (xabardor qilingan rozilik).

Rozilik o'qishga ta'sir qilmaydi: rozi bo'lmagan talaba platformadan to'liq foydalanadi, faqat uning
ma'lumotlari tadqiqot eksporti va tadqiqot statistikasiga (psixometrik tahlil, tajriba samaradorligi)
kirmaydi. Talaba qarorini istalgan payt profilida o'zgartira oladi; har bir qaror tarixda saqlanadi.

Rozilik matni o'zgarsa, CONSENT_VERSION oshiriladi: talabadan qayta so'raladi (oldingi qarori yangi
qaror berguncha amalda qoladi).
"""
from django.conf import settings
from django.db import transaction
from django.utils import timezone

CONSENT_VERSION = "1"

CONSENT_TITLE = "Ilmiy tadqiqotda ishtirok etishga rozilik"

CONSENT_TEXT = [
    "Bu platforma «Ma'lumotlar bazasini loyihalash» fanini o'qitishda virtual laboratoriya va sun'iy intellekt "
    "yordamchisi samaradorligini o'rganuvchi ilmiy tadqiqotda qo'llanmoqda.",
    "Tadqiqotda quyidagi ma'lumotlar ishlatiladi: laboratoriyalardagi urinishlar va baholar, kirish/chiqish "
    "testlari va so'rovnoma javoblari, AI maslahatlaridan foydalanish. Ismingiz, loginingiz va yozgan kodingiz "
    "tadqiqotchiga berilmaydi: siz faqat taxallus (masalan, T-1A2B3C4D) bilan ko'rsatilasiz. Natijalar faqat "
    "umumlashgan holda (guruhlar bo'yicha) e'lon qilinadi.",
    "Ishtirok ixtiyoriy. Rozi bo'lmasangiz ham platformadan to'liq foydalanasiz, bahoyingizga hech qanday ta'sir "
    "qilmaydi. Qaroringizni istalgan payt «Profil» sahifasida o'zgartirishingiz mumkin: rozilikni qaytarib "
    "olsangiz, ma'lumotlaringiz keyingi eksportlarga kirmaydi.",
]


def consent_required():
    return settings.RESEARCH_CONSENT_REQUIRED


def research_participants(users):
    """Tadqiqot hisob-kitoblariga kiradigan foydalanuvchilar (QuerySet): rozilik talab qilinsa — faqat rozi bo'lganlar."""
    return users.filter(research_consent=True) if consent_required() else users


def participant_ids():
    """Rozi bo'lgan talabalar id'lari to'plami; rozilik talab qilinmasa None (hamma kiradi)."""
    from .models import User

    if not consent_required():
        return None
    return set(User.objects.filter(role=User.Role.STUDENT, research_consent=True).values_list("pk", flat=True))


def needs_decision(user):
    """Talabadan rozilik so'ralishi kerakmi: hali qaror bermagan yoki rozilik matni yangilangan."""
    return bool(
        consent_required()
        and user.is_student
        and (user.research_consent is None or user.research_consent_version != CONSENT_VERSION)
    )


def status_payload(user):
    return {
        "required": consent_required(),
        "version": CONSENT_VERSION,
        "title": CONSENT_TITLE,
        "text": CONSENT_TEXT,
        "contact": settings.RESEARCH_CONTACT,
        "agreed": user.research_consent,
        "decided_at": user.research_consent_at,
        "needs_decision": needs_decision(user),
    }


def record_decision(user, agreed):
    """Qarorni foydalanuvchiga yozadi va tarixga qo'shadi."""
    from .models import ResearchConsent

    now = timezone.now()
    with transaction.atomic():
        user.research_consent = agreed
        user.research_consent_version = CONSENT_VERSION
        user.research_consent_at = now
        user.save(update_fields=["research_consent", "research_consent_version", "research_consent_at"])
        ResearchConsent.objects.create(user=user, agreed=agreed, version=CONSENT_VERSION, created_at=now)
    return user
