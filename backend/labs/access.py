"""Kim qaysi laboratoriyalarni ko'ra olishini belgilaydi."""
from learning.access import filter_visible

from .models import Lab


def visible_labs(user):
    return filter_visible(Lab.objects.all(), user)
