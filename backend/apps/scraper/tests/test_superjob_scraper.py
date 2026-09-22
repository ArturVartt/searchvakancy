import json
from pathlib import Path
from unittest.mock import patch

import pytest
from django.test import override_settings

from apps.jobs.models import Job, JobSource
from apps.scraper.superjob_scraper import SuperJobScraper

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "superjob_vacancies_response.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _run_with_key(fixture: dict):
    with (
        override_settings(SUPERJOB_API_KEY="test-key"),
        patch.object(SuperJobScraper, "_fetch_page", return_value=fixture),
    ):
        return SuperJobScraper().run()


@pytest.mark.django_db
def test_run_filters_irrelevant_and_closed_vacancies():
    stats = _run_with_key(load_fixture())

    # Из 4 карточек: одна не про frontend (менеджер по продажам),
    # одна закрыта (is_closed) — обе должны быть отфильтрованы.
    assert stats["fetched"] == 2
    assert stats["created"] == 2
    assert stats["errors"] == 0
    assert Job.objects.count() == 2
    assert not Job.objects.filter(external_id="52200999").exists()  # менеджер
    assert not Job.objects.filter(external_id="52201234").exists()  # закрыта
    assert JobSource.objects.filter(name="SuperJob", last_sync__isnull=False).exists()


@pytest.mark.django_db
def test_intern_job_fields():
    _run_with_key(load_fixture())

    job = Job.objects.get(external_id="52192592")
    assert job.title == "Стажёр Frontend-разработчик"
    assert job.company == "OZON: Старт карьеры"
    assert job.salary_from is None
    assert job.salary_to is None
    assert job.experience_level == Job.ExperienceLevel.JUNIOR
    assert job.job_type == Job.JobType.INTERNSHIP  # "Стажёр" в заголовке
    assert job.employment_type == Job.EmploymentType.FULL_DAY
    assert job.location == "Москва"
    assert job.required_skills == []
    assert job.url == "https://www.superjob.ru/vakansii/stazhjor-frontend-razrabotchik-52192592.html"
    assert job.posted_at is not None


@pytest.mark.django_db
def test_senior_remote_job_with_salary_and_skills():
    _run_with_key(load_fixture())

    job = Job.objects.get(external_id="52200001")
    # SuperJob отдаёт текст с неэкранированными HTML-сущностями
    # ("&amp;" вместо "&") — должны быть раскодированы.
    assert job.title == "Senior Frontend-разработчик (React & TypeScript)"
    assert job.salary_from == 250000
    assert job.salary_to == 350000
    assert job.currency == Job.Currency.RUB
    assert job.experience_level == Job.ExperienceLevel.SENIOR
    # "удалённая" встречается в описании -> REMOTE, несмотря на
    # type_of_work="Полный рабочий день"
    assert job.employment_type == Job.EmploymentType.REMOTE
    assert set(job.required_skills) == {"React", "TypeScript", "Redux"}


@pytest.mark.django_db
def test_fetch_raw_jobs_returns_empty_without_api_key():
    with override_settings(SUPERJOB_API_KEY=""):
        assert SuperJobScraper().fetch_raw_jobs() == []


@pytest.mark.django_db
def test_run_is_idempotent_on_rerun():
    fixture = load_fixture()
    _run_with_key(fixture)
    stats = _run_with_key(fixture)

    assert stats["created"] == 0
    assert stats["updated"] == 2
    assert stats["is_first_sync"] is False
    assert Job.objects.count() == 2
