from unittest.mock import patch

import pytest

from apps.jobs import tasks as jobs_tasks
from apps.jobs.tasks import run_all_scrapers, run_scraper


class _FakeScraper:
    def __init__(self, stats: dict):
        self._stats = stats

    def run(self) -> dict:
        return self._stats


@pytest.mark.django_db
def test_run_scraper_does_not_notify_on_first_sync(monkeypatch):
    """
    Первый прогон источника (JobSource.last_sync ещё не было) наполняет
    БД, но НЕ должен спамить Telegram-уведомлениями по всей истории разом.
    """
    stats = {
        "source": "Fake",
        "fetched": 1,
        "created": 1,
        "updated": 0,
        "errors": 0,
        "new_job_ids": [1],
        "is_first_sync": True,
    }
    monkeypatch.setitem(jobs_tasks.SCRAPERS, "fake", lambda: _FakeScraper(stats))

    with patch("apps.telegram_bot.tasks.notify_users_for_jobs.delay") as mocked_delay:
        result = run_scraper("fake")

    assert result == stats
    mocked_delay.assert_not_called()


@pytest.mark.django_db
def test_run_scraper_notifies_on_non_first_sync(monkeypatch):
    stats = {
        "source": "Fake",
        "fetched": 1,
        "created": 1,
        "updated": 0,
        "errors": 0,
        "new_job_ids": [2],
        "is_first_sync": False,
    }
    monkeypatch.setitem(jobs_tasks.SCRAPERS, "fake", lambda: _FakeScraper(stats))

    with patch("apps.telegram_bot.tasks.notify_users_for_jobs.delay") as mocked_delay:
        run_scraper("fake")

    mocked_delay.assert_called_once_with([2])


@pytest.mark.django_db
def test_run_all_scrapers_sends_one_combined_notify_call_across_sources(monkeypatch):
    """
    Регрессия: раньше каждый источник сам по себе вызывал
    notify_users_for_jobs.delay(...) внутри _run_one — если за один тик
    Celery Beat несколько источников находили новые вакансии, подписчик
    получил бы отдельное сообщение в Telegram на каждый источник. Теперь
    run_all_scrapers должен собрать new_job_ids со всех источников и
    отправить их ОДНИМ вызовом.
    """
    stats_a = {
        "source": "A",
        "fetched": 1,
        "created": 1,
        "updated": 0,
        "errors": 0,
        "new_job_ids": [1, 2],
        "is_first_sync": False,
    }
    stats_b = {
        "source": "B",
        "fetched": 1,
        "created": 1,
        "updated": 0,
        "errors": 0,
        "new_job_ids": [3],
        "is_first_sync": False,
    }
    monkeypatch.setattr(
        jobs_tasks,
        "SCRAPERS",
        {"a": lambda: _FakeScraper(stats_a), "b": lambda: _FakeScraper(stats_b)},
    )

    with patch("apps.telegram_bot.tasks.notify_users_for_jobs.delay") as mocked_delay:
        result = run_all_scrapers()

    assert result == {"a": stats_a, "b": stats_b}
    mocked_delay.assert_called_once_with([1, 2, 3])


@pytest.mark.django_db
def test_run_all_scrapers_skips_notify_call_when_nothing_new(monkeypatch):
    stats = {
        "source": "Fake",
        "fetched": 0,
        "created": 0,
        "updated": 0,
        "errors": 0,
        "new_job_ids": [],
        "is_first_sync": False,
    }
    monkeypatch.setattr(jobs_tasks, "SCRAPERS", {"fake": lambda: _FakeScraper(stats)})

    with patch("apps.telegram_bot.tasks.notify_users_for_jobs.delay") as mocked_delay:
        run_all_scrapers()

    mocked_delay.assert_not_called()
