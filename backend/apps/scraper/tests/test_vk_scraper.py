from pathlib import Path
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.jobs.models import Job, JobSource
from apps.scraper.vk_scraper import VKScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _run_with_fixtures():
    # Порядок side_effect соответствует порядку запросов в fetch_raw_jobs:
    # сперва список, затем detail-страницы в порядке ссылок из списка
    # (111, 222, 333 — см. vk_list_fragment.html). time.sleep между
    # detail-запросами мокаем, чтобы тест не ждал реальные секунды.
    with (
        patch.object(
            VKScraper,
            "_fetch",
            side_effect=[
                _fixture("vk_list_fragment.html"),
                _fixture("vk_detail_111_senior.html"),
                _fixture("vk_detail_222_remote.html"),
                _fixture("vk_detail_333_irrelevant.html"),
            ],
        ),
        patch("apps.scraper.vk_scraper.time.sleep"),
    ):
        return VKScraper().run()


@pytest.mark.django_db
def test_run_filters_irrelevant_and_saves_relevant():
    stats = _run_with_fixtures()

    # 3 detail-страницы забраны, но вакансия 333 ("Разработчик внутренних
    # инструментов", Go/Python, без фронтенд-ключевых слов) отсеивается
    # is_frontend_relevant() несмотря на то, что попала в specialty=287.
    assert stats["fetched"] == 2
    assert stats["created"] == 2
    assert stats["errors"] == 0
    assert Job.objects.count() == 2
    assert not Job.objects.filter(external_id="333").exists()
    assert JobSource.objects.filter(name="VK", last_sync__isnull=False).exists()


@pytest.mark.django_db
def test_senior_office_or_hybrid_job_fields():
    _run_with_fixtures()

    job = Job.objects.get(external_id="111")
    assert job.title == "Старший Frontend-разработчик в команду Core Frontend в ВКонтакте, Москва"
    assert job.company == "Mail.Ru Group, ВКонтакте"
    assert job.location == "Москва"
    assert job.experience_level == Job.ExperienceLevel.SENIOR
    # "Формат работы" включает офис/гибрид, не только "Дистанционный" ->
    # обычный полный день, а не REMOTE (см. _extract_employment_type).
    assert job.employment_type == Job.EmploymentType.FULL_DAY
    assert job.salary_from is None
    assert job.salary_to is None
    assert job.url == "https://team.vk.company/vacancy/111/"
    # make_aware интерпретирует "2026-09-22" как полночь по Europe/Moscow
    # (TIME_ZONE проекта) — сравниваем через localtime, а не сырой UTC .date()
    # (иначе из-за сдвига UTC+3 дата "съезжает" на 21-е).
    assert job.posted_at is not None
    assert timezone.localtime(job.posted_at).date().isoformat() == "2026-09-22"


@pytest.mark.django_db
def test_fully_remote_job_sets_remote_employment_type():
    _run_with_fixtures()

    job = Job.objects.get(external_id="222")
    assert job.company == "Mail.Ru Group, MAX"
    assert job.experience_level == Job.ExperienceLevel.MIDDLE
    # "Формат работы" — единственная опция "Дистанционный" -> REMOTE.
    assert job.employment_type == Job.EmploymentType.REMOTE


@pytest.mark.django_db
def test_run_is_idempotent_on_rerun():
    _run_with_fixtures()
    stats = _run_with_fixtures()

    assert stats["created"] == 0
    assert stats["updated"] == 2
    assert stats["is_first_sync"] is False
    assert Job.objects.count() == 2
