from django.contrib import admin

from .models import FavoriteJob, Job, JobNotification, JobSource, UserJobFilter


@admin.register(JobSource)
class JobSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "is_active", "last_sync")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "source",
        "experience_level",
        "location",
        "salary_from",
        "salary_to",
        "currency",
        "is_active",
        "posted_at",
    )
    list_filter = ("source", "experience_level", "job_type", "employment_type", "is_active")
    search_fields = ("title", "company", "description", "external_id")
    date_hierarchy = "posted_at"
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserJobFilter)
class UserJobFilterAdmin(admin.ModelAdmin):
    list_display = ("user", "min_salary", "max_salary", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("user__username", "user__email")


@admin.register(JobNotification)
class JobNotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "job", "notified_at", "sent_to_telegram", "is_read")
    list_filter = ("sent_to_telegram", "is_read")
    search_fields = ("user__username", "job__title")


@admin.register(FavoriteJob)
class FavoriteJobAdmin(admin.ModelAdmin):
    list_display = ("user", "job", "created_at")
    search_fields = ("user__username", "job__title")
