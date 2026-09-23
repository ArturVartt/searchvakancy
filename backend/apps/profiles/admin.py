from django.contrib import admin

from .models import ProfileSet


@admin.register(ProfileSet)
class ProfileSetAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "email", "phone", "updated_at")
    list_filter = ("user",)
    search_fields = ("name", "user__username", "email", "phone")
    readonly_fields = ("created_at", "updated_at")
