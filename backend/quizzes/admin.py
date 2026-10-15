from django.contrib import admin

from .models import Quiz, QuizAttempt


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "author", "opens_at", "closes_at", "created_at"]
    list_filter = ["kind"]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ["quiz", "student", "score", "max_score", "started_at", "submitted_at"]
    list_filter = ["quiz"]
