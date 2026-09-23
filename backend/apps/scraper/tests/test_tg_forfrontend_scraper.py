from pathlib import Path
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.jobs.models import Job, JobSource
from apps.scraper.tg_forfrontend_scraper import TgForFrontendScraper

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "tg_forfrontend_page.html"


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
        "apps.scraper.tg_forfrontend_scraper.requests.Session.get",
        return_value=_FakeResponse(html),
    ):
        return TgForFrontendScraper().run()


@pytest.mark.django_db
def test_run_filters_multi_position_fullstack_and_irrelevant_posts():
    stats = _run()

    # 4 поста в фикстуре, проходит только один (7376, FocusReactive):
    # 7374 (Wisebits) — исключён по "fullstack" в заголовке;
    # 7370 (GitLab) — дайджест на 2 позиции (маркер 🔹), пропускается целиком;
    # 7380 (Data Scientist) — вообще не про фронтенд.
    assert stats["fetched"] == 1
    assert stats["created"] == 1
    assert stats["errors"] == 0
    assert Job.objects.count() == 1
    assert not Job.objects.filter(external_id="7374").exists()
    assert not Job.objects.filter(external_id="7370").exists()
    assert not Job.objects.filter(external_id="7380").exists()
    assert JobSource.objects.filter(name="Job for Frontend (TG)", last_sync__isnull=False).exists()


@pytest.mark.django_db
def test_single_position_post_fields():
    _run()

    job = Job.objects.get(external_id="7376")
    assert job.title == "Strong Middle / Senior Developer (React/Next.js + Node.js)"
    assert job.company == "FocusReactive"
    assert job.location == "Remote work (Belarus, Poland, Georgia, Serbia)."
    assert "Jamstack" in job.description
    # Нет собственной ссылки-заявки — берём первую ссылку на LinkedIn из поста.
    assert job.url == "https://www.linkedin.com/posts/viktoria-example"
    assert job.posted_at is not None
    assert timezone.localtime(job.posted_at).strftime("%Y-%m-%d") == "2026-09-21"


@pytest.mark.django_db
def test_run_is_idempotent_on_rerun():
    _run()
    stats = _run()

    assert stats["created"] == 0
    assert stats["updated"] == 1
    assert stats["is_first_sync"] is False
    assert Job.objects.count() == 1
