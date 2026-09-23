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

    # Из 3 карточек одна — не про frontend (менеджер по продажам).
    assert stats["fetched"] == 2
    assert stats["created"] == 2
    assert stats["errors"] == 0
    assert Job.objects.count() == 2
    assert not Job.objects.filter(external_id="136900001").exists()
    assert JobSource.objects.filter(name="HH.uz", last_sync__isnull=False).exists()


@pytest.mark.django_db
def test_uzs_salary_and_absolute_url():
    _run_with_single_page(load_fixture_html())

    job = Job.objects.get(external_id="137527751")
    assert job.title == "Fullstack-разработчик"
    assert job.company == "ООО FAIR-METALL"
    assert job.location == "Ташкент, 2-й Джаркурганский проезд, 22А"
    assert job.experience_level == Job.ExperienceLevel.JUNIOR  # between1And3
    assert job.salary_from == 8000000
    assert job.salary_to is None
    assert job.currency == Job.Currency.UZS
    # href в фикстуре уже абсолютный (как реально отдаёт hh.uz, в отличие
    # от относительного у zarplata.ru) — url должен взяться как есть.
    assert job.url == "https://hh.uz/vacancy/137527751?query=frontend&hhtmFrom=vacancy_search_list"


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
    assert stats["updated"] == 2
    assert stats["is_first_sync"] is False
    assert Job.objects.count() == 2
