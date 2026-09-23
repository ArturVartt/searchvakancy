"""
Скрейпер Telegram-канала @remote_frontend_jobs — единственный TG-источник
в проекте. Исследование 23.09.2026 по ~47 каналам показало, что
подавляющее большинство перемешивают вакансии с рекламой/промо в
непредсказуемых форматах (см. README) — этот канал редкое исключение:
ведётся автоматически (судя по стилю — ботом-агрегатором, репостящим с
Upwork/Workable/Jobicy и т.п.), одна вакансия на пост, строгий шаблон
"Label: значение" без единого рекламного поста в выборке.

Публичное веб-превью `t.me/s/<channel>` — без бота, без логина, без
API-ключа. У `t.me` вообще нет `robots.txt` (404 на сам файл) —
ограничений на скрейпинг нет. Отдаёт только последние ~20 постов без
пагинации назад — при прогоне раз в 30 минут этого с запасом достаточно
(канал публикует примерно 1 вакансию в день).

Реальный HTML поста (`.tgme_widget_message_text`) — последовательность
`<b>Label</b>: значение<br/>`, поля: Published time / Company name /
Title / Salary (не всегда) / Grades / Job description / Location /
Anywhere / Remote / Forbidden locations (не всегда) / прямая ссылка
"👉👉( Job Description & Apply )👈👈" / Tags (хэштеги). Парсим построчно
state-machine'ом по `<b>`/`<br>`, НО хэштеги вытаскиваем отдельным
проходом по `a[href^="?q=%23"]` — в шаблоне `<br>` рвёт поле "Tags" сразу
после подписи (`<b>Tags</b>:<br/><a>#frontend</a>...`), так что общий
парсер полей увидел бы там пустое значение.

Зарплата — свободный текст ("$50,000 - $70,000 per year", "Up to $3200 /
month") — вытаскиваем первые 1-2 числа регэкспом, best-effort (не
покрывает все мыслимые формулировки, но так у большинства реальных
постов). Grades — список через запятую ("senior, senior+" или "junior,
junior+, middle") — берём МИНИМАЛЬНЫЙ уровень: это диапазон "от какого
грейда рассматривают", а не один грейд, и минимум ближе к "порогу входа".

`url` ведёт на прямую ссылку "Apply" из поста (это то, что пользователю
реально надо открыть), а не на сам пост в Telegram; сам пост —
запасной вариант, если по какой-то причине ссылки в посте нет.
"""
import logging
import re
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from django.utils import timezone

from apps.jobs.models import Job

from .base import BaseScraper
from .parser import is_frontend_relevant, strip_html

logger = logging.getLogger(__name__)

GRADE_RANK = {
    Job.ExperienceLevel.JUNIOR: 0,
    Job.ExperienceLevel.MIDDLE: 1,
    Job.ExperienceLevel.SENIOR: 2,
    Job.ExperienceLevel.LEAD: 3,
}
GRADE_MAP = {
    "junior": Job.ExperienceLevel.JUNIOR,
    "junior+": Job.ExperienceLevel.JUNIOR,
    "middle": Job.ExperienceLevel.MIDDLE,
    "middle+": Job.ExperienceLevel.MIDDLE,
    "senior": Job.ExperienceLevel.SENIOR,
    "senior+": Job.ExperienceLevel.SENIOR,
    "lead": Job.ExperienceLevel.LEAD,
}


class TgRemoteFrontendScraper(BaseScraper):
    source_name = "Remote Frontend Jobs (TG)"
    source_url = "https://t.me/s/remote_frontend_jobs"

    channel = "remote_frontend_jobs"
    preview_url = "https://t.me/s/remote_frontend_jobs"

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

        fields, apply_url = _parse_field_lines(text_el)
        title = fields.get("Title", "").strip()
        if not title:
            return None

        description = fields.get("Job description", "")
        if not is_frontend_relevant(title, description):
            return None

        tags = [a.get_text(strip=True) for a in text_el.select('a[href^="?q=%23"]')]

        company = fields.get("Company name", "")
        location = fields.get("Location", "")
        experience_level = _parse_grades(fields.get("Grades", ""))
        salary_from, salary_to, currency = _parse_salary(fields.get("Salary", ""))
        employment_type = (
            Job.EmploymentType.REMOTE if fields.get("Remote", "").strip().lower() == "yes" else Job.EmploymentType.FULL_DAY
        )
        posted_at = _parse_date(fields.get("Published time"))

        post_url = f"https://t.me/{self.channel}/{message_id}"

        return {
            "external_id": message_id,
            "title": title,
            "company": company,
            "description": strip_html(description),
            "salary_from": salary_from,
            "salary_to": salary_to,
            "currency": currency,
            "location": location,
            "job_type": "",
            "experience_level": experience_level,
            "employment_type": employment_type,
            "required_skills": tags,
            "nice_to_have": [],
            "url": apply_url or post_url,
            "posted_at": posted_at,
            "is_active": True,
        }

    def normalize_job(self, raw: dict[str, Any]) -> dict[str, Any]:
        # _parse_message уже собрал финальный словарь под поля Job.
        return raw


def _parse_field_lines(text_el: Tag) -> tuple[dict[str, str], str | None]:
    """
    Проходит по прямым children `.tgme_widget_message_text` как по
    state machine: `<b>` начинает новое поле, `<br>` его завершает,
    остальное (текст, `<a>` со ссылкой на #хэштег) — накапливается как
    значение текущего поля. Внешняя ссылка "Apply" (href на настоящий
    URL, не на "?q=#тег") встречается вне какого-либо поля — ловим её
    отдельно, а не как значение.
    """
    fields: dict[str, str] = {}
    apply_url: str | None = None
    current_label: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current_label, buffer
        if current_label is not None:
            fields[current_label] = "".join(buffer).strip(" :\n")
        current_label = None
        buffer = []

    for child in text_el.contents:
        name = getattr(child, "name", None)
        if name == "br":
            flush()
        elif name == "b":
            flush()
            current_label = child.get_text(strip=True)
        elif name == "a":
            href = child.get("href", "")
            if href.startswith("http") and current_label is None:
                apply_url = href
            else:
                buffer.append(child.get_text())
        elif name == "i":
            continue  # emoji-иконки, не текст
        else:
            buffer.append(str(child))
    flush()

    return fields, apply_url


def _parse_grades(value: str) -> str:
    levels = []
    for token in value.split(","):
        level = GRADE_MAP.get(token.strip().lower())
        if level:
            levels.append(level)
    if not levels:
        return ""
    return min(levels, key=lambda level: GRADE_RANK[level])


def _parse_salary(value: str) -> tuple[int | None, int | None, str]:
    if not value:
        return None, None, Job.Currency.USD
    numbers = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", value)]
    if len(numbers) >= 2:
        return numbers[0], numbers[1], Job.Currency.USD
    if len(numbers) == 1:
        if "up to" in value.lower():
            return None, numbers[0], Job.Currency.USD
        return numbers[0], None, Job.Currency.USD
    return None, None, Job.Currency.USD


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        naive = datetime.strptime(value.strip(), "%Y-%m-%d")
    except ValueError:
        return None
    return timezone.make_aware(naive)
