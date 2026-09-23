from pathlib import Path
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.jobs.models import Job, JobSource
from apps.scraper.tg_remote_frontend_scraper import TgRemoteFrontendScraper

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "tg_remote_frontend_page.html"


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        pass


def load_fixture_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def _run():
    html = load_fixture_html()
    with patch(
        "apps.scraper.tg_remote_frontend_scraper.requests.Session.get",
        return_value=_FakeResponse(html),
    ):
        return TgRemoteFrontendScraper().run()


@pytest.mark.django_db
def test_run_filters_fullstack_and_irrelevant_posts():
    stats = _run()

    # 4 поста забраны, но отсеиваются два: "Full-stack Node + React" (id
    # 941 — исключён FRONTEND_EXCLUDE_KEYWORDS по слову "full-stack" в
    # заголовке) и "Senior DevOps Engineer" (id 943 — вообще не про
    # фронтенд).
    assert stats["fetched"] == 2
    assert stats["created"] == 2
    assert stats["errors"] == 0
    assert Job.objects.count() == 2
    assert not Job.objects.filter(external_id="941").exists()
    assert not Job.objects.filter(external_id="943").exists()
    assert JobSource.objects.filter(name="Remote Frontend Jobs (TG)", last_sync__isnull=False).exists()


@pytest.mark.django_db
def test_single_salary_treated_as_upper_bound_and_grade_range_takes_minimum():
    _run()

    job = Job.objects.get(external_id="939")
    assert job.title == "Frontend Developer (React / Shopify Hydrogen)"
    assert job.company == "Lago"
    assert job.location == "Eastern Europe"
    # "Up to $3200 / month" -> верхняя граница, не нижняя.
    assert job.salary_from is None
    assert job.salary_to == 3200
    assert job.currency == Job.Currency.USD
    # "middle+, senior" -> берём минимальный уровень диапазона.
    assert job.experience_level == Job.ExperienceLevel.MIDDLE
    assert job.employment_type == Job.EmploymentType.REMOTE
    assert job.required_skills == ["#frontend", "#react", "#shopify"]
    # url ведёт на прямую ссылку "Apply" из поста, не на сам пост в Telegram.
    assert job.url == "https://apply.workable.com/lago-1/j/A99E34437C"


@pytest.mark.django_db
def test_salary_range_and_posted_date():
    _run()

    job = Job.objects.get(external_id="942")
    assert job.salary_from == 50000
    assert job.salary_to == 70000
    assert job.experience_level == Job.ExperienceLevel.SENIOR  # "senior, senior+" -> senior
    assert job.url == "https://wantapply.com/senior-frontend-engineer-react-at-easyship"
    assert job.posted_at is not None
    assert timezone.localtime(job.posted_at).strftime("%Y-%m-%d") == "2026-09-22"


@pytest.mark.django_db
def test_run_is_idempotent_on_rerun():
    _run()
    stats = _run()

    assert stats["created"] == 0
    assert stats["updated"] == 2
    assert stats["is_first_sync"] is False
    assert Job.objects.count() == 2
