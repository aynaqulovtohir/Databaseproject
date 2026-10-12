from django.contrib import admin

from .models import Grade


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ["submission", "score", "ai_suggested_score", "graded_by", "graded_at"]
    readonly_fields = ["submission", "ai_suggested_score", "graded_by", "graded_at", "updated_at"]
