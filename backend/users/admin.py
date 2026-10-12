from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import StudentGroup, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ["username", "first_name", "last_name", "role", "group", "is_active"]
    list_filter = ["role", "group", "is_active"]
    fieldsets = DjangoUserAdmin.fieldsets + (("Rol va guruh", {"fields": ("role", "group")}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (("Rol va guruh", {"fields": ("role", "group")}),)


@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]
    filter_horizontal = ["teachers"]
