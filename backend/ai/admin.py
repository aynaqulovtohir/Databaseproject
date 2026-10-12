from django.contrib import admin

from .models import AIAnalysis

# ChatMessage ataylab ro'yxatga olinmagan: yozishmalarni faqat talabaning o'zi ko'radi.


@admin.register(AIAnalysis)
class AIAnalysisAdmin(admin.ModelAdmin):
    list_display = ["submission", "status", "suggested_score", "attempts", "created_at", "completed_at"]
    list_filter = ["status"]
    readonly_fields = [field.name for field in AIAnalysis._meta.fields]
