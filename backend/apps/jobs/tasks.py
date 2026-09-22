import logging

from celery import shared_task

from apps.scraper.registry import SCRAPERS

logger = logging.getLogger(__name__)


def _run_one(source_key: str) -> dict:
    scraper_cls = SCRAPERS.get(source_key)
    if scraper_cls is None:
        raise ValueError(f"Unknown scraper key: {source_key!r}. Known: {list(SCRAPERS)}")
    stats = scraper_cls().run()
    logger.info("Scraper %s finished: %s", source_key, stats)
    return stats


def _notifiable_job_ids(source_key: str, stats: dict) -> list[int]:
    """Новые вакансии источника, которые стоит слать в Telegram — то есть
    не из самого первого прогона источника (см. is_first_sync в
    BaseScraper.run(): иначе первый же подписчик получил бы спам из всей
    найденной истории разом)."""
    new_job_ids = stats.get("new_job_ids") or []
    if not new_job_ids:
        return []
    if stats.get("is_first_sync"):
        logger.info(
            "Scraper %s: первый прогон источника, %s вакансий сохранены без уведомлений",
            source_key,
            len(new_job_ids),
        )
        return []
    return new_job_ids


def _dispatch_notifications(job_ids: list[int]) -> None:
    if not job_ids:
        return
    # Локальный импорт — иначе apps.jobs.tasks <-> apps.telegram_bot.tasks
    # не зациклятся, а apps.telegram_bot вообще не обязан существовать,
    # чтобы скрейпинг работал (Phase 2 не зависит от Phase 3).
    from apps.telegram_bot.tasks import notify_users_for_jobs

    notify_users_for_jobs.delay(job_ids)


@shared_task
def run_scraper(source_key: str) -> dict:
    """Запустить один конкретный скрейпер по ключу из apps.scraper.registry.SCRAPERS."""
    stats = _run_one(source_key)
    _dispatch_notifications(_notifiable_job_ids(source_key, stats))
    return stats


@shared_task
def run_all_scrapers() -> dict:
    """
    Запускает все зарегистрированные скрейперы по очереди (по расписанию,
    см. CELERY_BEAT_SCHEDULE) и уведомляет об их новых вакансиях ОДНИМ
    вызовом notify_users_for_jobs — не по вызову на источник. Источников
    пять; если бы каждый слал уведомления сам по себе, подписчик мог бы
    получить за один тик несколько отдельных сообщений в Telegram (по
    одному на источник, который что-то нашёл) вместо одной сводки за
    эти полчаса.
    """
    results: dict[str, dict] = {}
    all_new_job_ids: list[int] = []
    for key in SCRAPERS:
        stats = _run_one(key)
        results[key] = stats
        all_new_job_ids.extend(_notifiable_job_ids(key, stats))

    _dispatch_notifications(all_new_job_ids)
    return results
