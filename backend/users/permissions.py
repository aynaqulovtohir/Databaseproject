"""Rolga asoslangan ruxsat tekshiruvchilari."""
from rest_framework.permissions import BasePermission

from config.i18n import N_


class IsAdmin(BasePermission):
    message = N_("Bu amal faqat admin uchun.")

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class IsTeacher(BasePermission):
    message = N_("Bu amal faqat o'qituvchi uchun.")

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_teacher)


class IsStudent(BasePermission):
    message = N_("Bu amal faqat talaba uchun.")

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_student)
