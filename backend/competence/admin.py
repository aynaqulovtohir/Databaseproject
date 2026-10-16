from django.contrib import admin

from .models import Component, Indicator


class IndicatorInline(admin.StackedInline):
    model = Indicator
    extra = 0
    fields = ["order", "name", "source", "weight", "topics", "initial_quizzes", "final_quizzes", "delayed_quizzes"]
    filter_horizontal = ["initial_quizzes", "final_quizzes", "delayed_quizzes"]


@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    list_display = ["name", "order", "medium_from", "high_from"]
    list_editable = ["order"]
    inlines = [IndicatorInline]
