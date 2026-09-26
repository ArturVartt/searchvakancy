from django.conf import settings
from django.db import models
from django.utils import timezone


class Application(models.Model):
    class Status(models.TextChoices):
        SAVED = "saved", "Сохранено"
        APPLIED = "applied", "Откликнулся"
        INTERVIEW = "interview", "Собеседование"
        OFFER = "offer", "Оффер"
        REJECTED = "rejected", "Отказ"

    # Статусы, при которых отклик уже отправлен — от них зависит applied_at.
    SENT_STATUSES = (Status.APPLIED, Status.INTERVIEW, Status.OFFER, Status.REJECTED)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications")
    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, related_name="applications")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.APPLIED)
    profile_set = models.ForeignKey(
        "profiles.ProfileSet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
    )
    note = models.TextField(blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Отклик"
        verbose_name_plural = "Отклики"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "job"], name="unique_application_per_user_job"),
        ]

    def save(self, *args, **kwargs):
        if self.status in self.SENT_STATUSES and self.applied_at is None:
            self.applied_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user} → {self.job_id} ({self.status})"
