import json
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.jobs.models import Job, JobSource
from apps.scraper.hh_scraper import HHScraper

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "hh_search_response.json"


def load_fixture() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.django_db
def test_run_creates_jobs_and_normalizes_fields():
    with patch.object(HHScraper, "fetch_raw_jobs", return_value=load_fixture()):
        stats = HHScraper().run()

    new_job_ids = stats.pop("new_job_ids")
    assert stats == {
        "source": "HH.ru",
        "fetched": 2,
        "created": 2,
        "updated": 0,
        "errors": 0,
        "is_first_sync": True,
    }
    assert sorted(new_job_ids) == sorted(Job.objects.values_list("id", flat=True))
    assert JobSource.objects.filter(name="HH.ru", last_sync__isnull=False).exists()

    senior_job = Job.objects.get(external_id="111111111")
    assert senior_job.title == "Frontend-разработчик (React)"
    assert senior_job.company == "ООО Ромашка"
    assert senior_job.salary_from == 180000
    assert senior_job.salary_to == 260000
    assert senior_job.currency == Job.Currency.RUB
    assert senior_job.location == "Москва"
    assert senior_job.job_type == Job.JobType.FULL_TIME
    assert senior_job.experience_level == Job.ExperienceLevel.MIDDLE
    assert senior_job.employment_type == Job.EmploymentType.REMOTE
    assert "React" in senior_job.description
    assert "<highlighttext>" not in senior_job.description  # HTML вычищен

    junior_job = Job.objects.get(external_id="222222222")
    assert junior_job.experience_level == Job.ExperienceLevel.JUNIOR
    assert junior_job.job_type == Job.JobType.INTERNSHIP
    assert junior_job.salary_from is None


@pytest.mark.django_db
def test_run_is_idempotent_and_updates_existing_jobs():
    fixture = load_fixture()
    with patch.object(HHScraper, "fetch_raw_jobs", return_value=fixture):
        HHScraper().run()

    updated_fixture = load_fixture()
    updated_fixture[0]["name"] = "Frontend-разработчик (React) — обновлено"

    with patch.object(HHScraper, "fetch_raw_jobs", return_value=updated_fixture):
        stats = HHScraper().run()

    assert stats["created"] == 0
    assert stats["updated"] == 2
    assert stats["is_first_sync"] is False  # last_sync уже был выставлен первым run()
    assert Job.objects.count() == 2  # дедуп по (source, external_id), не дублируем
    assert Job.objects.get(external_id="111111111").title.endswith("обновлено")
