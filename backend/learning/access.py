"""Kim nimani ko'ra olishini bitta joyda belgilaydi."""
from .models import Assignment, Material


def filter_visible(queryset, user):
    """Admin — hammasi, o'qituvchi — o'zi yaratganlari, talaba — o'z guruhiga berilganlar."""
    if user.is_admin:
        return queryset
    if user.is_teacher:
        return queryset.filter(author=user)
    # Talaba: faqat o'z guruhiga berilganlar
    if user.group_id is None:
        return queryset.none()
    return queryset.filter(groups=user.group_id)


def visible_materials(user):
    return filter_visible(Material.objects.all(), user)


def visible_assignments(user):
    return filter_visible(Assignment.objects.all(), user)
