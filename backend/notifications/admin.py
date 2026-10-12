from django.contrib import admin

from .models import Notification, TelegramAccount


@admin.register(TelegramAccount)
class TelegramAccountAdmin(admin.ModelAdmin):
    list_display = ["user", "linked_at"]
    readonly_fields = ["user", "chat_id", "linked_at"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "kind", "status", "attempts", "created_at", "sent_at"]
    list_filter = ["kind", "status"]
    readonly_fields = [field.name for field in Notification._meta.fields]
