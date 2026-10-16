from django.contrib import admin

from .models import Lab, LabAttempt, LabGrade, PeerReview


@admin.register(Lab)
class LabAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "created_at"]
    search_fields = ["title"]
    filter_horizontal = ["groups"]


@admin.register(LabAttempt)
class LabAttemptAdmin(admin.ModelAdmin):
    list_display = ["lab", "student", "is_correct", "created_at"]
    list_filter = ["is_correct"]
    readonly_fields = ["lab", "student", "sql_code", "is_correct", "feedback", "ai_advice", "ai_requested_at", "created_at"]


@admin.register(LabGrade)
class LabGradeAdmin(admin.ModelAdmin):
    list_display = ["lab", "student", "score", "source", "graded_at"]
    list_filter = ["source"]
    readonly_fields = ["lab", "student", "attempt", "graded_at"]


@admin.register(PeerReview)
class PeerReviewAdmin(admin.ModelAdmin):
    """Moderatsiya: nomaqbul izohni ko'rib, o'chirish mumkin (baholar o'zgartirilmaydi)."""

    list_display = ["attempt", "reviewer", "helpful", "created_at"]
    list_filter = ["attempt__lab", "helpful"]
    readonly_fields = ["attempt", "reviewer", "scores", "comment", "reference_ratio", "helpful", "created_at"]

    def has_add_permission(self, request):
        return False
