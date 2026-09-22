from pathlib import Path
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from apps.jobs.models import Job, JobSource
from apps.scraper.zarplata_scraper import ZarplataScraper

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "zarplata_vacancies_page.html"


def load_fixture_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def _run_with_single_page(html: str):
    """fetch_raw_jobs пагинирует через _fetch_page — на первой "пустой"
    следующей странице цикл останавливается сам."""
    with (
        patch.object(ZarplataScraper, "_fetch_page", side_effect=[html, ""]),
        patch("apps.scraper.zarplata_scraper.time.sleep"),
    ):
        return ZarplataScraper().run()


@pytest.mark.django_db
def test_run_parses_real_markup_and_filters_off_topic_card():
    stats = _run_with_single_page(load_fixture_html())

    # Из 4 карточек одна — не про frontend (менеджер по продажам).
    assert stats["fetched"] == 3
    assert stats["created"] == 3
    assert stats["errors"] == 0
    assert Job.objects.count() == 3
    assert not Job.objects.filter(external_id="137700099").exists()
    assert JobSource.objects.filter(name="Zarplata.ru", last_sync__isnull=False).exists()


@pytest.mark.django_db
def test_vue_job_no_salary_no_remote():
    _run_with_single_page(load_fixture_html())

    job = Job.objects.get(external_id="137651428")
    assert job.title == "Frontend-разработчик Vue.js"
    assert job.company == "Мой Кассир"
    assert job.location == "Москва"
    assert job.experience_level == Job.ExperienceLevel.JUNIOR  # between1And3
    assert job.employment_type == ""  # чипа "удалённо" не было
    assert job.salary_from is None
    assert job.salary_to is None
    assert job.url == "https://zarplata.ru/vacancy/137651428?query=Frontend&hhtmFrom=vacancy_search_list"


@pytest.mark.django_db
def test_remote_job_with_salary_range():
    _run_with_single_page(load_fixture_html())

    job = Job.objects.get(external_id="137700002")
    assert job.salary_from == 180000
    assert job.salary_to == 240000
    assert job.currency == Job.Currency.RUB
    assert job.experience_level == Job.ExperienceLevel.MIDDLE  # between3And6
    assert job.employment_type == Job.EmploymentType.REMOTE
    assert "React/Vue" in job.description


@pytest.mark.django_db
def test_single_value_salary_treated_as_lower_bound():
    _run_with_single_page(load_fixture_html())

    job = Job.objects.get(external_id="137700555")
    assert job.salary_from == 300000
    assert job.salary_to is None
    assert job.experience_level == Job.ExperienceLevel.SENIOR  # moreThan6


def test_parse_salary_distinguishes_amount_from_experience_data_tags():
    # Регрессия на реальный баг: и зарплата, и опыт рендерятся через
    # <data value="...">, поэтому нельзя просто брать "первый <data>".
    card = BeautifulSoup(
        """
        <article>
          <data value="1-3">Опыт 1-3 года</data>
          <data value="150000">150 000</data><data value="RUB">₽</data>
        </article>
        """,
        "lxml",
    ).find("article")
    assert ZarplataScraper._parse_salary(card) == (150000, None, Job.Currency.RUB)


@pytest.mark.django_db
def test_run_is_idempotent_on_rerun():
    html = load_fixture_html()
    _run_with_single_page(html)
    stats = _run_with_single_page(html)

    assert stats["created"] == 0
    assert stats["updated"] == 3
    assert stats["is_first_sync"] is False
    assert Job.objects.count() == 3
