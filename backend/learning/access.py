"""Kim nimani ko'ra olishini bitta joyda belgilaydi."""
from .models import Assignment, Material


def _visible(queryset, user):
    if user.is_admin:
        return queryset
    if user.is_teacher:
        return queryset.filter(author=user)
    # Talaba: faqat o'z guruhiga berilganlar
    if user.group_id is None:
        return queryset.none()
    return queryset.filter(groups=user.group_id)


def visible_materials(user):
    return _visible(Material.objects.all(), user)


def visible_assignments(user):
    return _visible(Assignment.objects.all(), user)
