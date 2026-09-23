from pathlib import Path
from unittest.mock import patch

import pytest

from apps.jobs.models import Job, JobSource
from apps.scraper.hh_scraper import HHScraper

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "hh_vacancies_page.html"


def load_fixture_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def _run_with_single_page(html: str):
    """fetch_raw_jobs пагинирует через _fetch_page — на первой "пустой"
    следующей странице цикл останавливается сам. time.sleep мокаем —
    иначе тест ждал бы реальные "человеческие" паузы (см. HUMAN_DELAY_RANGE
    в hh_scraper.py)."""
    with (
        patch.object(HHScraper, "_fetch_page", side_effect=[html, ""]),
        patch("apps.scraper.hh_scraper.time.sleep"),
    ):
        return HHScraper().run()


@pytest.mark.django_db
def test_run_parses_real_markup_and_filters_off_topic_card():
    stats = _run_with_single_page(load_fixture_html())

    # Из 3 карточек одна — не про frontend (Senior Data Scientist).
    assert stats["fetched"] == 2
    assert stats["created"] == 2
    assert stats["errors"] == 0
    assert Job.objects.count() == 2
    assert not Job.objects.filter(external_id="333333333").exists()
    assert JobSource.objects.filter(name="HH.ru", last_sync__isnull=False).exists()


@pytest.mark.django_db
def test_remote_job_with_salary_range():
    _run_with_single_page(load_fixture_html())

    job = Job.objects.get(external_id="111111111")
    assert job.title == "Frontend-разработчик (React)"
    assert job.company == "ООО Ромашка"
    assert job.location == "Москва"
    assert job.experience_level == Job.ExperienceLevel.MIDDLE  # between3And6
    assert job.employment_type == Job.EmploymentType.REMOTE
    assert job.salary_from == 180000
    assert job.salary_to == 260000
    assert job.currency == Job.Currency.RUB
    assert job.url == "https://hh.ru/vacancy/111111111?query=frontend&hhtmFrom=vacancy_search_list"


@pytest.mark.django_db
def test_intern_job_no_salary_matched_via_snippet_keywords():
    _run_with_single_page(load_fixture_html())

    # Заголовок "Стажер Frontend-разработчик" уже содержит "Frontend", но
    # заодно проверяем, что сниппет (HTML/CSS/JavaScript) тоже учитывается.
    job = Job.objects.get(external_id="222222222")
    assert job.experience_level == Job.ExperienceLevel.JUNIOR  # noExperience
    assert job.salary_from is None
    assert job.salary_to is None
    assert job.employment_type == ""  # чипа "удалённо" не было


@pytest.mark.django_db
def test_run_is_idempotent_on_rerun():
    html = load_fixture_html()
    _run_with_single_page(html)
    stats = _run_with_single_page(html)

    assert stats["created"] == 0
    assert stats["updated"] == 2
    assert stats["is_first_sync"] is False
    assert Job.objects.count() == 2
