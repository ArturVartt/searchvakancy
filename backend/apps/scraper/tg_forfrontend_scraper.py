"""
Скрейпер Telegram-канала @forfrontend ("Job for Frontend (JavaScript +
Node.js) Developers") — второй TG-источник в проекте, см. общий подход в
tg_remote_frontend_scraper.py (публичное веб-превью `t.me/s/<канал>`,
без бота/логина/API-ключа, у `t.me` нет `robots.txt`).

В отличие от @remote_frontend_jobs, здесь нет единого шаблона
"Label: значение" — посты это репосты вакансий с LinkedIn в свободной
форме. Проверено вживую 23.09.2026: у "одиночных" постов (одна вакансия)
структура всё же стабильна позиционно — первые три прямых `<b>`-child
`.tgme_widget_message_text`: заголовок, компания (+ описание компании
обычным текстом сразу после), локация/формат работы (иногда несколько
`<b>`-сегментов подряд — берём все целиком).

НО часть постов — "дайджест" на несколько вакансий сразу в одном
сообщении, помеченный эмодзи 🔹 перед каждой позицией (например,
"🔹Engineering Manager 🔹Frontend Engineer" у одной компании). Разбивать
такой пост на несколько записей значило бы либо путать поля между
вакансиями, либо городить отдельный парсер под сам этот дайджест-формат
ради, по факту, меньшинства постов — вместо этого такие посты просто
пропускаются (детектируется по наличию символа "🔹" в тексте поста).
Это осознанный компромисс: часть вакансий канала не попадает в базу,
зато то, что попадает, размечено надёжно, а не приблизительно.

Явной даты публикации в тексте поста нет (в отличие от
@remote_frontend_jobs) — используем `time[datetime]` самого
Telegram-сообщения (`.tgme_widget_message_date`), это есть у каждого
поста независимо от формата содержимого.

Прямой ссылки "Apply" на саму вакансию, как у @remote_frontend_jobs, тоже
нет — есть только ссылка на LinkedIn-пост рекрутёра ("post on LinkedIn")
или на текст вакансии ("Job description"). Берём первую ссылку на
`linkedin.com`, найденную в посте, как лучшее доступное приближение к
"куда идти за подробностями"; если такой ссылки почему-то нет — открываем
сам пост в Telegram.
"""
import logging
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from django.utils.dateparse import parse_datetime

from apps.jobs.models import Job

from .base import BaseScraper
from .parser import is_frontend_relevant, strip_html

logger = logging.getLogger(__name__)

MULTI_POSITION_MARKER = "🔹"


class TgForFrontendScraper(BaseScraper):
    source_name = "Job for Frontend (TG)"
    source_url = "https://t.me/s/forfrontend"

    channel = "forfrontend"
    preview_url = "https://t.me/s/forfrontend"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "SearchVakancy/1.0 (+https://github.com/searchvakancy)",
                "Accept": "text/html",
            }
        )

    def fetch_raw_jobs(self) -> list[dict[str, Any]]:
        response = self.session.get(self.preview_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        items: list[dict[str, Any]] = []
        for message in soup.select(".tgme_widget_message"):
            raw = self._parse_message(message)
            if raw is not None:
                items.append(raw)
        return items

    def _parse_message(self, message: Tag) -> dict[str, Any] | None:
        data_post = message.get("data-post", "")
        message_id = data_post.rsplit("/", 1)[-1] if "/" in data_post else ""
        if not message_id.isdigit():
            return None

        text_el = message.select_one(".tgme_widget_message_text")
        if text_el is None:
            return None

        # Дайджест на несколько вакансий сразу — пропускаем, см. докстринг.
        if MULTI_POSITION_MARKER in text_el.get_text():
            return None

        bolds = text_el.find_all("b", recursive=False)
        if len(bolds) < 3:
            return None

        title = bolds[0].get_text(strip=True)
        company = bolds[1].get_text(strip=True)
        location = " ".join(b.get_text(strip=True) for b in bolds[2:])

        company_blurb = _text_after(bolds[1])

        if not title or not company:
            return None

        description = strip_html(company_blurb)
        if not is_frontend_relevant(title, description):
            return None

        detail_url = None
        for a in text_el.find_all("a"):
            href = a.get("href", "")
            if "linkedin.com" in href:
                detail_url = href
                break

        post_url = f"https://t.me/{self.channel}/{message_id}"

        return {
            "external_id": message_id,
            "title": title,
            "company": company,
            "description": description,
            "salary_from": None,
            "salary_to": None,
            "currency": Job.Currency.USD,
            "location": location,
            "job_type": "",
            "experience_level": "",
            "employment_type": "",
            "required_skills": [],
            "nice_to_have": [],
            "url": detail_url or post_url,
            "posted_at": _parse_message_date(message),
            "is_active": True,
        }

    def normalize_job(self, raw: dict[str, Any]) -> dict[str, Any]:
        # _parse_message уже собрал финальный словарь под поля Job.
        return raw


def _text_after(tag: Tag) -> str:
    """Текст обычных (не `<b>`) узлов сразу после tag, до первого `<br>`."""
    parts: list[str] = []
    for sibling in tag.next_siblings:
        name = getattr(sibling, "name", None)
        if name == "br":
            break
        if name == "b":
            break
        parts.append(sibling if isinstance(sibling, str) else sibling.get_text())
    return "".join(parts).strip()


def _parse_message_date(message: Tag) -> datetime | None:
    time_el = message.select_one(".tgme_widget_message_date time")
    if time_el is None:
        return None
    return parse_datetime(time_el.get("datetime", ""))
