from django.contrib import admin

from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("user", "job", "status", "profile_set", "applied_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("user__username", "job__title", "job__company")
    readonly_fields = ("created_at", "updated_at")
