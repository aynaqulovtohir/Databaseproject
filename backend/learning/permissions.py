from rest_framework.permissions import SAFE_METHODS, BasePermission

from config.i18n import N_


class IsStaffRoleOrReadOnly(BasePermission):
    """O'qish — kirgan har bir foydalanuvchiga; o'zgartirish — admin va o'qituvchiga."""

    message = N_("Bu amal faqat admin yoki o'qituvchi uchun.")

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.is_admin or user.is_teacher
