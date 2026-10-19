"""Imtihon rejimi: modulga imtihon vaqti (exam_starts_at — exam_ends_at) belgilanadi.

Talaba uchun shu moduldagi laboratoriyalar:
- imtihondan oldin — yopiq (sharti ham ko'rsatilmaydi);
- imtihon paytida — ishlash mumkin, lekin AI yordami (maslahat, murabbiy, tushuntirish, reja, tavsiya) va o'zaro
  baholash o'chiriladi; ball AI'siz (avtomatik) qo'yiladi; ER'ning tuzatilgan diagrammasi imtihon tugaguncha
  ko'rsatilmaydi (u to'g'ri javobni ochadi);
- imtihondan keyin — ko'rish va AI yordami ochiq, lekin tekshirish va topshirish yopiq.
Admin va o'qituvchi uchun cheklov yo'q.
"""
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

UPCOMING, ACTIVE, FINISHED = "upcoming", "active", "finished"
# Murojaat turlari: ko'rish, ishlash (tekshirish, topshirish), AI yordami
VIEW, WORK, AI = "view", "work", "ai"


def exam_state(module, now=None):
    if module is None or module.exam_starts_at is None or module.exam_ends_at is None:
        return None
    now = now or timezone.now()
    if now < module.exam_starts_at:
        return UPCOMING
    if now < module.exam_ends_at:
        return ACTIVE
    return FINISHED


def lab_exam_state(lab):
    return exam_state(lab.module) if lab.module_id else None


def exam_active(lab):
    return lab_exam_state(lab) == ACTIVE


def exam_info(module):
    state = exam_state(module)
    if state is None:
        return None
    return {"starts_at": module.exam_starts_at, "ends_at": module.exam_ends_at, "state": state}


def _local(moment):
    return timezone.localtime(moment).strftime("%d.%m.%Y %H:%M")


def ensure_exam(user, lab, kind=VIEW):
    """Talaba uchun imtihon qoidasini buzadigan murojaatda PermissionDenied (403)."""
    if not user.is_student:
        return
    state = lab_exam_state(lab)
    if state == UPCOMING:
        raise PermissionDenied(f"Imtihon {_local(lab.module.exam_starts_at)} da boshlanadi.")
    if state == ACTIVE and kind == AI:
        raise PermissionDenied("Imtihon davomida AI yordami va o'zaro baholash o'chirilgan.")
    if state == FINISHED and kind == WORK:
        raise PermissionDenied(f"Imtihon {_local(lab.module.exam_ends_at)} da tugagan: yechimni endi yuborib bo'lmaydi.")
