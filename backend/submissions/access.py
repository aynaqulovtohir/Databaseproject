"""Kim qaysi yechimlarni ko'ra olishini belgilaydi."""
from .models import Submission


def visible_submissions(user):
    queryset = Submission.objects.select_related("student", "assignment", "grade")
    if user.is_admin:
        return queryset
    if user.is_teacher:
        # Faqat o'zi yaratgan topshiriqlarga kelgan yechimlar
        return queryset.filter(assignment__author=user)
    # Talaba: faqat o'z yechimlari
    return queryset.filter(student=user)
