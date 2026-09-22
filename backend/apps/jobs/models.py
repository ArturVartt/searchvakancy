from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import F


class JobSource(models.Model):
    """Источник вакансий: HH.ru, VK Jobs, Habr Career и т.д."""

    name = models.CharField(max_length=100, unique=True)
    url = models.URLField()
    icon = models.CharField(max_length=255, blank=True, help_text="URL иконки источника")
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Источник вакансий"
        verbose_name_plural = "Источники вакансий"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Job(models.Model):
    class Currency(models.TextChoices):
        RUB = "RUB", "₽ RUB"
        USD = "USD", "$ USD"
        EUR = "EUR", "€ EUR"

    class JobType(models.TextChoices):
        FULL_TIME = "full_time", "Постоянная"
        CONTRACT = "contract", "Контракт"
        FREELANCE = "freelance", "Фриланс"
        INTERNSHIP = "internship", "Стажировка"

    class ExperienceLevel(models.TextChoices):
        JUNIOR = "junior", "Junior"
        MIDDLE = "middle", "Middle"
        SENIOR = "senior", "Senior"
        LEAD = "lead", "Lead"

    class EmploymentType(models.TextChoices):
        FULL_DAY = "full_day", "Полный день"
        PART_TIME = "part_time", "Частичная занятость"
        REMOTE = "remote", "Удалённо"

    source = models.ForeignKey(JobSource, on_delete=models.CASCADE, related_name="jobs")

    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    salary_from = models.PositiveIntegerField(null=True, blank=True)
    salary_to = models.PositiveIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.RUB)

    location = models.CharField(max_length=255, blank=True)
    job_type = models.CharField(max_length=20, choices=JobType.choices, blank=True)
    experience_level = models.CharField(max_length=20, choices=ExperienceLevel.choices, blank=True)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices, blank=True)

    required_skills = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    nice_to_have = ArrayField(models.CharField(max_length=100), default=list, blank=True)

    url = models.URLField(max_length=1000)
    external_id = models.CharField(max_length=255, help_text="ID вакансии у источника")

    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Вакансия"
        verbose_name_plural = "Вакансии"
        # Без явного nulls_last Postgres сортирует NULL как "больше любого
        # значения" при DESC — то есть вакансии без posted_at (например,
        # Zarplata.ru не отдаёт дату публикации в списке) оказались бы
        # ВЫШЕ реально свежих вакансий с настоящей датой.
        ordering = [F("posted_at").desc(nulls_last=True), "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"],
                name="unique_job_per_source",
            )
        ]
        indexes = [
            models.Index(fields=["source", "-created_at"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["external_id"]),
            models.Index(fields=["experience_level"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} @ {self.company}"


class UserJobFilter(models.Model):
    """Пользовательский фильтр для подбора вакансий и Telegram-уведомлений."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_filters"
    )

    min_salary = models.PositiveIntegerField(null=True, blank=True)
    max_salary = models.PositiveIntegerField(null=True, blank=True)

    locations = ArrayField(models.CharField(max_length=255), default=list, blank=True)
    experience_levels = ArrayField(
        models.CharField(max_length=20, choices=Job.ExperienceLevel.choices),
        default=list,
        blank=True,
    )
    keywords = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    excluded_keywords = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    job_types = ArrayField(
        models.CharField(max_length=20, choices=Job.JobType.choices),
        default=list,
        blank=True,
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Фильтр вакансий"
        verbose_name_plural = "Фильтры вакансий"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"Фильтр #{self.pk} ({self.user})"

    def matches(self, job: Job) -> bool:
        """Проверить, подходит ли вакансия под этот фильтр (Phase 2/3)."""
        if self.min_salary and (job.salary_to or job.salary_from or 0) < self.min_salary:
            return False
        if self.max_salary and (job.salary_from or job.salary_to or 0) > self.max_salary:
            return False
        if self.experience_levels and job.experience_level not in self.experience_levels:
            return False
        if self.job_types and job.job_type not in self.job_types:
            return False
        if self.locations and job.location not in self.locations:
            return False

        haystack = f"{job.title} {job.description}".lower()
        if self.keywords and not any(kw.lower() in haystack for kw in self.keywords):
            return False
        if self.excluded_keywords and any(kw.lower() in haystack for kw in self.excluded_keywords):
            return False
        return True


class JobNotification(models.Model):
    """История уведомлений пользователя о вакансиях."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_notifications"
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="notifications")

    notified_at = models.DateTimeField(auto_now_add=True)
    sent_to_telegram = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Уведомление о вакансии"
        verbose_name_plural = "Уведомления о вакансиях"
        ordering = ["-notified_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "job"],
                name="unique_notification_per_user_job",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} <- {self.job}"


class FavoriteJob(models.Model):
    """
    Избранная вакансия пользователя. В исходном плане не было отдельной
    моделью (только API-эндпоинты POST/DELETE /api/jobs/<id>/favorite/),
    но без неё избранное негде хранить на сервере — добавлена в Phase 4.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorite_jobs"
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Избранная вакансия"
        verbose_name_plural = "Избранные вакансии"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "job"],
                name="unique_favorite_per_user_job",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} ★ {self.job}"
