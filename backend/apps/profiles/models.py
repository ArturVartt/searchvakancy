import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

RESUME_EXTENSIONS = ["pdf", "doc", "docx"]
RESUME_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 МБ — с запасом для обычного резюме


def resume_upload_path(instance: "ProfileSet", filename: str) -> str:
    # Случайное имя файла, а не оригинальное — чтобы путь в /media/ не был
    # предсказуемым (там телефон/email в самом файле, media отдаётся без
    # проверки прав, см. config/urls.py).
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    return f"resumes/{instance.user_id}/{name}"


def validate_resume_size(file) -> None:
    if file.size > RESUME_MAX_SIZE_BYTES:
        raise ValidationError(f"Файл резюме не должен превышать {RESUME_MAX_SIZE_BYTES // (1024 * 1024)} МБ.")


class ProfileSet(models.Model):
    """
    Именованный набор контактных данных + резюме, чтобы удобно хранить
    несколько разных резюме (например, под разные направления/языки) и
    быстро выбирать нужный при отклике на вакансию.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile_sets"
    )

    name = models.CharField(max_length=100, help_text="Название сета, например «Frontend RU» или «Backend EN»")
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    resume = models.FileField(
        upload_to=resume_upload_path,
        validators=[FileExtensionValidator(RESUME_EXTENSIONS), validate_resume_size],
    )
    github_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Сет профиля"
        verbose_name_plural = "Сеты профиля"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.user})"
