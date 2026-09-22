from pathlib import Path
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.jobs.models import Job, JobSource
from apps.scraper.staffam_scraper import StaffAmScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _run_with_fixtures():
    # Порядок side_effect: список (страница 1), список (страница 2, пустая
    # -> пагинация останавливается), затем detail-страницы в порядке
    # id 1001/1002/1003/1004 из staffam_list_page1.html. time.sleep мокаем,
    # чтобы тест не ждал реальные секунды.
    with (
        patch.object(
            StaffAmScraper,
            "_fetch",
            side_effect=[
                _fixture("staffam_list_page1.html"),
                _fixture("staffam_list_page2_empty.html"),
                _fixture("staffam_detail_1001_frontend.html"),
                _fixture("staffam_detail_1002_fullstack.html"),
                _fixture("staffam_detail_1003_devops.html"),
                _fixture("staffam_detail_1004_dotnet_mentions_frontend.html"),
            ],
        ),
        patch("apps.scraper.staffam_scraper.time.sleep"),
    ):
        return StaffAmScraper().run()


@pytest.mark.django_db
def test_run_filters_irrelevant_and_saves_relevant():
    stats = _run_with_fixtures()

    # 4 detail-страницы забраны (banner itemType=0 пропущен на этапе
    # списка), но отсеиваются две: "Senior DevOps Engineer" (id 1003, вообще
    # без фронтенд-слов) и "Senior .Net Engineer" (id 1004 — TypeScript/
    # Angular упомянуты только в описании как "будет плюсом", в skills их
    # нет — см. докстринг модуля про этот конкретный ложный срабатывание).
    assert stats["fetched"] == 2
    assert stats["created"] == 2
    assert stats["errors"] == 0
    assert Job.objects.count() == 2
    assert not Job.objects.filter(external_id="1003").exists()
    assert not Job.objects.filter(external_id="1004").exists()
    assert JobSource.objects.filter(name="Staff.am", last_sync__isnull=False).exists()


@pytest.mark.django_db
def test_frontend_titled_job_fields():
    _run_with_fixtures()

    job = Job.objects.get(external_id="1001")
    assert job.title == "Senior Frontend Engineer (Angular)"
    assert job.company == "Buymie"
    assert job.location == "Yerevan"
    assert job.experience_level == Job.ExperienceLevel.SENIOR
    assert job.employment_type == Job.EmploymentType.FULL_DAY
    assert job.job_type == Job.JobType.FULL_TIME
    assert job.salary_from is None and job.salary_to is None
    assert job.currency == Job.Currency.AMD
    # skills type=1 (soft skills, "Teamwork") не попадают в required_skills.
    assert job.required_skills == ["JavaScript", "AngularJS"]
    assert job.url == "https://staff.am/en/jobs/software-development/senior-frontend-engineer-angular-4"
    assert timezone.localtime(job.posted_at).strftime("%Y-%m-%d %H:%M:%S") == "2026-09-15 10:50:18"


@pytest.mark.django_db
def test_generic_title_job_matched_via_hard_skills_and_remote():
    _run_with_fixtures()

    # "Full Stack Developer" не содержит фронтенд-ключевых слов в
    # заголовке — прошёл только благодаря is_frontend_relevant() по
    # тегированным hard skills (type=2 "React"), а не по тексту описания
    # (см. докстринг модуля про ложные срабатывания на "упомянуто вскользь").
    job = Job.objects.get(external_id="1002")
    assert job.company == "Digitain"
    assert job.experience_level == Job.ExperienceLevel.MIDDLE
    assert job.employment_type == Job.EmploymentType.REMOTE  # is_remote=true
    assert job.salary_from == 400000
    assert job.salary_to == 600000
    assert job.required_skills == ["React", "Node.js"]


@pytest.mark.django_db
def test_run_is_idempotent_on_rerun():
    _run_with_fixtures()
    stats = _run_with_fixtures()

    assert stats["created"] == 0
    assert stats["updated"] == 2
    assert stats["is_first_sync"] is False
    assert Job.objects.count() == 2
