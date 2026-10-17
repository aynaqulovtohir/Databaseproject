from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import ResearchConsent, StudentGroup, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ["username", "first_name", "last_name", "role", "group", "research_consent", "is_active"]
    list_filter = ["role", "group", "research_consent", "is_active"]
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Rol va guruh", {"fields": ("role", "group")}),
        # Rozilikni faqat talabaning o'zi beradi yoki qaytarib oladi
        ("Tadqiqotga rozilik", {"fields": ("research_consent", "research_consent_version", "research_consent_at")}),
    )
    readonly_fields = ["research_consent", "research_consent_version", "research_consent_at"]
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (("Rol va guruh", {"fields": ("role", "group")}),)


@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]
    filter_horizontal = ["teachers"]


@admin.register(ResearchConsent)
class ResearchConsentAdmin(admin.ModelAdmin):
    """Faqat ko'rish: tarix o'zgartirilmaydi."""

    list_display = ["user", "agreed", "version", "created_at"]
    list_filter = ["agreed", "version"]
    search_fields = ["user__username"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
