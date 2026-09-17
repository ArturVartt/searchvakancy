from django.contrib.auth.models import AbstractUser
from django.db import models


class Customer(AbstractUser):
    """
    Пользователь приложения. Расширяем стандартного Django-юзера полями,
    нужными для Telegram-уведомлений (Phase 3).
    """

    telegram_chat_id = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="chat_id пользователя в Telegram, заполняется после /start в боте",
    )
    telegram_username = models.CharField(max_length=150, blank=True)
    telegram_notifications_enabled = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self) -> str:
        return self.username or self.email or f"customer#{self.pk}"
