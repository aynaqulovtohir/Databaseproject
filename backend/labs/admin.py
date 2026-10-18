from django.contrib import admin

from .models import Lab, LabAttempt, LabGrade, LabModule, PeerReview


@admin.register(Lab)
class LabAdmin(admin.ModelAdmin):
    list_display = ["title", "module", "position", "level", "author", "created_at"]
    list_filter = ["module"]
    search_fields = ["title"]
    filter_horizontal = ["groups"]


class ModuleLabInline(admin.TabularInline):
    model = Lab
    fields = ["title", "position", "level"]
    readonly_fields = ["title"]
    extra = 0
    can_delete = False
    ordering = ["position", "id"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LabModule)
class LabModuleAdmin(admin.ModelAdmin):
    list_display = ["title", "order", "sequential", "author"]
    inlines = [ModuleLabInline]


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
