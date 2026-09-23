from pathlib import Path
from unittest.mock import patch

import pytest

from apps.jobs.models import Job, JobSource
from apps.scraper.hhuz_scraper import HHUzScraper

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "hhuz_vacancies_page.html"


def load_fixture_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def _run_with_single_page(html: str):
    """fetch_raw_jobs пагинирует через _fetch_page — на первой "пустой"
    следующей странице цикл останавливается сам. time.sleep мокаем —
    иначе тест ждал бы реальные "человеческие" паузы (см. HUMAN_DELAY_RANGE
    в hhuz_scraper.py)."""
    with (
        patch.object(HHUzScraper, "_fetch_page", side_effect=[html, ""]),
        patch("apps.scraper.hhuz_scraper.time.sleep"),
    ):
        return HHUzScraper().run()


@pytest.mark.django_db
def test_run_parses_real_markup_and_filters_off_topic_card():
    stats = _run_with_single_page(load_fixture_html())

    # Из 3 карточек проходят: одна фронтенд-вакансия. Отсеиваются две —
    # "Менеджер по продажам" (не про frontend) и "Fullstack-разработчик"
    # (исключена по FRONTEND_EXCLUDE_KEYWORDS, несмотря на React/Node.js
    # в сниппете — см. test_fullstack_titled_job_is_excluded ниже).
    assert stats["fetched"] == 1
    assert stats["created"] == 1
    assert stats["errors"] == 0
    assert Job.objects.count() == 1
    assert not Job.objects.filter(external_id="136900001").exists()
    assert not Job.objects.filter(external_id="137527751").exists()
    assert JobSource.objects.filter(name="HH.uz", last_sync__isnull=False).exists()


@pytest.mark.django_db
def test_fullstack_titled_job_is_excluded():
    _run_with_single_page(load_fixture_html())

    # "Fullstack-разработчик" содержит и "React, Node.js" в сниппете, и
    # формально попал бы под FRONTEND_KEYWORDS ("react") — но
    # FRONTEND_EXCLUDE_KEYWORDS ("fullstack") отсеивает его первым.
    assert not Job.objects.filter(external_id="137527751").exists()


@pytest.mark.django_db
def test_usd_salary_range_and_remote():
    _run_with_single_page(load_fixture_html())

    job = Job.objects.get(external_id="136908753")
    assert job.salary_from == 300
    assert job.salary_to == 700
    assert job.currency == Job.Currency.USD
    assert job.employment_type == Job.EmploymentType.REMOTE


@pytest.mark.django_db
def test_run_is_idempotent_on_rerun():
    html = load_fixture_html()
    _run_with_single_page(html)
    stats = _run_with_single_page(html)

    assert stats["created"] == 0
    assert stats["updated"] == 1
    assert stats["is_first_sync"] is False
    assert Job.objects.count() == 1
