"""Laboratoriyalarni modullar bo'yicha ketma-ket ochish.

Zanjir: ketma-ket (sequential) modullardagi talabaga berilgan laboratoriyalar — modul tartibi (order), so'ng
moduldagi o'rni (position) bo'yicha. Zanjirdagi laboratoriya undan oldingi hamma laboratoriyalar yechilganda
ochiladi ("yechilgan" — tekshiruvdan kamida bir marta to'g'ri o'tgan). Modulsiz va ketma-ket bo'lmagan
moduldagi laboratoriyalar har doim ochiq.

Qulf faqat talabaga qo'llanadi va serverda tekshiriladi: qulflangan laboratoriyaning sharti ham, kodni
ishga tushirish ham, AI yordami ham berilmaydi.
"""
from rest_framework import status
from rest_framework.exceptions import APIException

from .models import LabAttempt


def chain_key(lab):
    return (lab.module.order, lab.module_id, lab.position, lab.pk)


def chain(labs):
    """Ketma-ket ochiladigan laboratoriyalar tartib bilan."""
    return sorted((lab for lab in labs if lab.module_id and lab.module.sequential), key=chain_key)


def solved_ids(student, labs=None):
    attempts = LabAttempt.objects.filter(student=student, is_correct=True)
    if labs is not None:
        attempts = attempts.filter(lab__in=labs)
    return set(attempts.values_list("lab_id", flat=True))


def lock_map(student, labs):
    """{lab_id: qulflagan laboratoriya (birinchi yechilmagan oldingisi) yoki None}. labs — talabaga ko'rinadiganlar."""
    labs = list(labs)
    result = {lab.pk: None for lab in labs}
    ordered = chain(labs)
    if not ordered:
        return result
    solved = solved_ids(student, ordered)
    blocker = None
    for lab in ordered:
        result[lab.pk] = blocker
        if blocker is None and lab.pk not in solved:
            blocker = lab
    return result


class LabLocked(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "lab_locked"

    def __init__(self, blocker):
        super().__init__()
        # DRF lug'at qiymatlarini matnga aylantirib yuboradi; locked va id o'z turida qolishi uchun to'g'ridan-to'g'ri
        self.detail = {
            "detail": f"Bu laboratoriya hali yopiq: avval «{blocker.title}» laboratoriyasini yeching.",
            "locked": True,
            "blocked_by": {"id": blocker.pk, "title": blocker.title},
        }


def ensure_unlocked(user, lab):
    """Talaba uchun qulflangan laboratoriyada LabLocked (403) chiqaradi; xodimlar uchun cheklov yo'q."""
    if not user.is_student or not lab.module_id:
        return
    from .access import visible_labs

    labs = visible_labs(user).select_related("module")
    blocker = lock_map(user, labs).get(lab.pk)
    if blocker is not None:
        raise LabLocked(blocker)
