from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Telegram",
            {
                "fields": (
                    "telegram_chat_id",
                    "telegram_username",
                    "telegram_notifications_enabled",
                )
            },
        ),
    )
    list_display = UserAdmin.list_display + ("telegram_notifications_enabled",)
