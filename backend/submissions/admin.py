from django.contrib import admin

from .models import Submission


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ["assignment", "student", "attempt_number", "status", "is_late", "submitted_at"]
    list_filter = ["status", "is_late"]
    readonly_fields = ["assignment", "student", "sql_code", "attempt_number", "is_late", "submitted_at"]
