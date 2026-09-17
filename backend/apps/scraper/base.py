"""
Общий контракт для скрейперов источников вакансий.

Чтобы добавить новый источник — наследуемся от BaseScraper и реализуем
fetch_raw_jobs() + normalize_job(); апсерт в БД, дедуп по (source,
external_id), WebSocket-рассылка и обновление last_sync делает run().
Ядро приложения (tasks.py, consumers.py) при этом не меняется —
см. "Расширяемость" в плане.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any

from django.utils import timezone

from apps.jobs.consumers import broadcast_job_event
from apps.jobs.models import Job, JobSource

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    #: должно совпадать с JobSource.name (используется для get_or_create)
    source_name: str
    #: URL источника, используется только при первом создании JobSource
    source_url: str

    def get_or_create_source(self) -> JobSource:
        source, _ = JobSource.objects.get_or_create(
            name=self.source_name, defaults={"url": self.source_url}
        )
        return source

    @abstractmethod
    def fetch_raw_jobs(self) -> list[dict[str, Any]]:
        """Получить сырые вакансии от источника (REST API / HTML)."""

    @abstractmethod
    def normalize_job(self, raw: dict[str, Any]) -> dict[str, Any]:
        """
        Привести сырую вакансию к словарю с полями модели Job
        (без source/created_at/updated_at — их проставляет _save_job).
        Обязателен ключ "external_id".
        """

    def run(self) -> dict[str, int | str]:
        """Полный цикл: fetch -> normalize -> upsert -> broadcast."""
        source = self.get_or_create_source()
        # last_sync ещё не выставлен -> это первый прогон этого источника:
        # его вакансии просто наполняют сайт/бота, но НЕ должны улетать как
        # Telegram-уведомления (иначе подписчик получит спам из всей истории
        # разом). Уведомления начинаются со второго и последующих прогонов.
        is_first_sync = source.last_sync is None
        stats: dict[str, int | str | bool | list[int]] = {
            "source": self.source_name,
            "fetched": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
            "new_job_ids": [],
            "is_first_sync": is_first_sync,
        }

        try:
            raw_jobs = self.fetch_raw_jobs()
        except Exception:
            logger.exception("Scraper %s: fetch_raw_jobs failed", self.source_name)
            stats["errors"] = 1
            return stats

        stats["fetched"] = len(raw_jobs)

        for raw in raw_jobs:
            try:
                normalized = self.normalize_job(raw)
                job, created = self._save_job(source, normalized)
                if created:
                    stats["created"] += 1
                    stats["new_job_ids"].append(job.id)
                else:
                    stats["updated"] += 1
            except Exception:
                logger.exception(
                    "Scraper %s: failed to process a raw job: %r", self.source_name, raw
                )
                stats["errors"] += 1

        source.last_sync = timezone.now()
        source.save(update_fields=["last_sync"])
        return stats

    def _save_job(self, source: JobSource, normalized: dict[str, Any]) -> tuple[Job, bool]:
        external_id = normalized["external_id"]
        defaults = {k: v for k, v in normalized.items() if k != "external_id"}

        job, created = Job.objects.update_or_create(
            source=source,
            external_id=external_id,
            defaults=defaults,
        )

        broadcast_job_event(
            "new" if created else "updated",
            {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "salary_from": job.salary_from,
                "salary_to": job.salary_to,
                "currency": job.currency,
                "url": job.url,
                "source": source.name,
            },
        )
        return job, created
