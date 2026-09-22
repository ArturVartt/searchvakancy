from pathlib import Path
from unittest.mock import patch

import pytest

from apps.jobs.models import Job, JobSource
from apps.scraper.itjobsuz_scraper import ItJobsUzScraper

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "itjobsuz_page_fragment.txt"


def load_fixture_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def _run_with_fixture(html: str):
    with patch.object(ItJobsUzScraper, "_fetch_page", return_value=html):
        return ItJobsUzScraper().run()


@pytest.mark.django_db
def test_run_filters_by_category_and_relevance():
    stats = _run_with_fixture(load_fixture_html())

    # 4 блока: "Фронтенд"/React (явная категория), "Бэкенд"/Python
    # (не про фронтенд — отфильтрован), "Фронтенд"/смешанная вакансия
    # (явная категория несмотря на общий заголовок), "Данные и ML"
    # (не про фронтенд — отфильтрован).
    assert stats["fetched"] == 2
    assert stats["created"] == 2
    assert stats["errors"] == 0
    assert Job.objects.count() == 2
    assert not Job.objects.filter(external_id="cjob0002office").exists()
    assert not Job.objects.filter(external_id="cjob0004mlengineer").exists()
    assert JobSource.objects.filter(name="IT-Jobs.uz", last_sync__isnull=False).exists()


@pytest.mark.django_db
def test_remote_react_job_fields():
    _run_with_fixture(load_fixture_html())

    job = Job.objects.get(external_id="cjob0001remote")
    assert job.title == "React.js Frontend-разработчик"
    assert job.company == "TechStart"
    assert job.salary_from is None
    assert job.salary_to == 1000
    assert job.currency == Job.Currency.USD
    assert job.experience_level == Job.ExperienceLevel.MIDDLE
    assert job.employment_type == Job.EmploymentType.REMOTE
    assert job.location == "Узбекистан"  # location=null в исходнике -> дефолт
    assert job.url == "https://it-jobs.uz/ru/jobs/react-js-frontend-razrabotchik-techstart-1001"
    assert job.posted_at is not None and job.posted_at.year == 2026


@pytest.mark.django_db
def test_uzs_salary_and_office_work_type():
    _run_with_fixture(load_fixture_html())

    job = Job.objects.get(external_id="cjob0003mixed")
    assert job.salary_from == 15000000
    assert job.salary_to == 18000000
    assert job.currency == Job.Currency.UZS
    assert job.employment_type == Job.EmploymentType.FULL_DAY  # workType=OFFICE
    assert job.experience_level == ""  # ANY -> неизвестно


@pytest.mark.django_db
def test_run_is_idempotent_on_rerun():
    html = load_fixture_html()
    _run_with_fixture(html)
    stats = _run_with_fixture(html)

    assert stats["created"] == 0
    assert stats["updated"] == 2
    assert stats["is_first_sync"] is False
    assert Job.objects.count() == 2
