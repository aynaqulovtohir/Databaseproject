from django.contrib import admin

from .models import Assignment, Material, MaterialFile


class MaterialFileInline(admin.TabularInline):
    model = MaterialFile
    extra = 0
    readonly_fields = ["original_name", "size", "uploaded_at"]


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "created_at"]
    search_fields = ["title"]
    filter_horizontal = ["groups"]
    inlines = [MaterialFileInline]


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "deadline", "created_at"]
    search_fields = ["title"]
    filter_horizontal = ["groups"]
