from pathlib import Path
from unittest.mock import patch

import pytest

from apps.jobs.models import Job, JobSource
from apps.scraper.uzum_scraper import UzumScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _run_with_fixtures():
    # Порядок side_effect: sitemap.xml, затем detail-страницы в порядке
    # обнаруженных ссылок (1001/1002/1003 — только /career/ru/, дубли
    # /career/uz/ на те же ID из sitemap игнорируются на этапе discovery,
    # к ним ни одного запроса не идёт). time.sleep мокаем.
    with (
        patch.object(
            UzumScraper,
            "_fetch",
            side_effect=[
                _fixture("uzum_sitemap.xml"),
                _fixture("uzum_detail_1001_frontend.html"),
                _fixture("uzum_detail_1002_backend.html"),
                _fixture("uzum_detail_1003_fullstack.html"),
            ],
        ),
        patch("apps.scraper.uzum_scraper.time.sleep"),
    ):
        return UzumScraper().run()


@pytest.mark.django_db
def test_run_filters_backend_and_fullstack_keeps_frontend():
    stats = _run_with_fixtures()

    # 3 detail-страницы забраны (только ru-локаль из sitemap, uz-дубли
    # тех же ID не запрашиваются вообще). Отсеиваются: "Senior Go
    # Developer" (id 1002, не про фронтенд) и "Junior Fullstack Developer"
    # (id 1003, исключён по FRONTEND_EXCLUDE_KEYWORDS несмотря на React
    # в описании).
    assert stats["fetched"] == 1
    assert stats["created"] == 1
    assert stats["errors"] == 0
    assert Job.objects.count() == 1
    assert not Job.objects.filter(external_id="1002").exists()
    assert not Job.objects.filter(external_id="1003").exists()
    assert JobSource.objects.filter(name="Uzum", last_sync__isnull=False).exists()


@pytest.mark.django_db
def test_frontend_job_fields():
    _run_with_fixtures()

    job = Job.objects.get(external_id="1001")
    assert job.title == "Senior Frontend Developer (Uzum Market)"
    assert job.company == "Uzum Market"
    assert job.location == "Ташкент"
    assert job.employment_type == Job.EmploymentType.FULL_DAY  # "Гибридный"
    assert job.experience_level == Job.ExperienceLevel.MIDDLE  # "От 3 лет"
    assert job.salary_from is None and job.salary_to is None
    assert job.currency == Job.Currency.UZS
    assert "React" in job.description
    assert job.url == "https://people.uzum.com/career/ru/vacancies/1001"
    # Кнопки "Откликнуться"/"Поделиться" не должны попасть в описание.
    assert "Откликнуться" not in job.description


@pytest.mark.django_db
def test_run_is_idempotent_on_rerun():
    _run_with_fixtures()
    stats = _run_with_fixtures()

    assert stats["created"] == 0
    assert stats["updated"] == 1
    assert stats["is_first_sync"] is False
    assert Job.objects.count() == 1


def test_parse_experience_buckets():
    from apps.scraper.uzum_scraper import _parse_experience

    assert _parse_experience("Без опыта") == Job.ExperienceLevel.JUNIOR
    assert _parse_experience("От 1 года") == Job.ExperienceLevel.JUNIOR
    assert _parse_experience("От 3 лет") == Job.ExperienceLevel.MIDDLE
    assert _parse_experience("От 6 лет") == Job.ExperienceLevel.SENIOR
