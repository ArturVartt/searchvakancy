from pathlib import Path
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from apps.jobs.models import Job, JobSource
from apps.scraper.habr_scraper import HabrScraper

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "habr_vacancies_page.html"


def load_fixture_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def _run_with_single_page(html: str):
    """fetch_raw_jobs пагинирует через _fetch_page — на первой "пустой"
    следующей странице цикл останавливается сам (см. HabrScraper.fetch_raw_jobs).
    time.sleep между страницами мокаем, чтобы тест не ждал реальную секунду."""
    with (
        patch.object(HabrScraper, "_fetch_page", side_effect=[html, ""]),
        patch("apps.scraper.habr_scraper.time.sleep"),
    ):
        return HabrScraper().run()


@pytest.mark.django_db
def test_run_parses_real_markup_and_filters_off_topic_card():
    stats = _run_with_single_page(load_fixture_html())

    # Из трёх карточек в фикстуре одна — не про frontend (Senior C++) и
    # должна быть отфильтрована is_frontend_relevant.
    assert stats["fetched"] == 2
    assert stats["created"] == 2
    assert stats["errors"] == 0
    assert Job.objects.count() == 2
    assert not Job.objects.filter(external_id="1000168749").exists()

    assert JobSource.objects.filter(name="Habr Career", last_sync__isnull=False).exists()


@pytest.mark.django_db
def test_vue_job_fields_parsed_correctly():
    _run_with_single_page(load_fixture_html())

    job = Job.objects.get(external_id="1000168747")
    assert job.title == "Frontend-разработчик (Vue.js)"
    assert job.company == "Мой Кассир"
    assert job.salary_from == 200000
    assert job.salary_to is None
    assert job.currency == Job.Currency.RUB
    assert job.experience_level == Job.ExperienceLevel.MIDDLE
    assert job.employment_type == Job.EmploymentType.REMOTE
    assert job.location == "Удалённо"  # нет placemark-чипа, но "удалённо" в формате
    assert set(job.required_skills) == {"Vue.js", "TypeScript", "Английский язык"}
    assert job.url == "https://career.habr.com/vacancies/1000168747"
    assert job.posted_at is not None and job.posted_at.year == 2026


@pytest.mark.django_db
def test_intern_job_with_placemark_and_upper_bound_salary():
    _run_with_single_page(load_fixture_html())

    job = Job.objects.get(external_id="1000170001")
    assert job.salary_from is None
    assert job.salary_to == 150000
    assert job.experience_level == Job.ExperienceLevel.JUNIOR  # Intern -> junior
    assert job.location == "Санкт-Петербург"
    assert job.employment_type == ""  # чипа "формат" не было
    assert set(job.required_skills) == {"React", "JavaScript"}


@pytest.mark.parametrize(
    ("salary_html", "expected"),
    [
        ("от 200 000 ₽", (200000, None, Job.Currency.RUB)),
        ("до 188 000 ₽", (None, 188000, Job.Currency.RUB)),
        # Реальный формат диапазона на живом Habr — словами "от X до Y",
        # НЕ через тире. Раньше это склеивало оба числа в одно
        # (70000150000) и падало на PositiveIntegerField.
        ("от 70 000 до 150 000 ₽", (70000, 150000, Job.Currency.RUB)),
        ("от 2000 до 3000 $", (2000, 3000, Job.Currency.USD)),
        ("до 5000 $", (None, 5000, Job.Currency.USD)),
        ("150 000 ₽", (150000, 150000, Job.Currency.RUB)),
    ],
)
def test_parse_salary_handles_real_habr_formats(salary_html, expected):
    card = BeautifulSoup(
        f'<div class="vacancy-card"><div class="basic-salary">{salary_html}</div></div>',
        "lxml",
    )
    assert HabrScraper._parse_salary(card) == expected


def test_parse_salary_returns_none_when_salary_not_specified():
    card = BeautifulSoup(
        '<div class="vacancy-card"><h4 class="predicted-salary__title">Зарплата не указана</h4></div>',
        "lxml",
    )
    assert HabrScraper._parse_salary(card) == (None, None, Job.Currency.RUB)


@pytest.mark.django_db
def test_run_is_idempotent_on_rerun():
    _run_with_single_page(load_fixture_html())
    stats = _run_with_single_page(load_fixture_html())

    assert stats["created"] == 0
    assert stats["updated"] == 2
    assert stats["is_first_sync"] is False
    assert Job.objects.count() == 2
