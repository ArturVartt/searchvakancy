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

    new_job_ids = stats.get("new_job_ids") or []
    if new_job_ids and stats.get("is_first_sync"):
        logger.info(
            "Scraper %s: первый прогон источника, %s вакансий сохранены без уведомлений",
            source_key,
            len(new_job_ids),
        )
    elif new_job_ids:
        # Локальный импорт — иначе apps.jobs.tasks <-> apps.telegram_bot.tasks
        # не зациклятся, а apps.telegram_bot вообще не обязан существовать,
        # чтобы скрейпинг работал (Phase 2 не зависит от Phase 3).
        from apps.telegram_bot.tasks import notify_users_for_jobs

        notify_users_for_jobs.delay(new_job_ids)

    return stats


@shared_task
def run_scraper(source_key: str) -> dict:
    """Запустить один конкретный скрейпер по ключу из apps.scraper.registry.SCRAPERS."""
    return _run_one(source_key)


@shared_task
def run_all_scrapers() -> dict:
    """Запустить все зарегистрированные скрейперы по очереди (вызывается по расписанию)."""
    return {key: _run_one(key) for key in SCRAPERS}


# Уведомления (проверка UserJobFilter.matches() по новым вакансиям + отправка
# в Telegram) добавляются в Phase 3, когда появится apps.telegram_bot.
