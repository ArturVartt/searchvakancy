from unittest.mock import patch

import pytest

from apps.jobs import tasks as jobs_tasks
from apps.jobs.tasks import _run_one


class _FakeScraper:
    def __init__(self, stats: dict):
        self._stats = stats

    def run(self) -> dict:
        return self._stats


@pytest.mark.django_db
def test_run_one_does_not_notify_on_first_sync(monkeypatch):
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
        result = _run_one("fake")

    assert result == stats
    mocked_delay.assert_not_called()


@pytest.mark.django_db
def test_run_one_notifies_on_non_first_sync(monkeypatch):
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
        _run_one("fake")

    mocked_delay.assert_called_once_with([2])
