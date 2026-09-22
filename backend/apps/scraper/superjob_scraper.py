"""
Скрейпер SuperJob через официальный REST API (api.superjob.ru/2.0/vacancies/).

В отличие от HH.ru (закрыли публичный доступ — см. hh_scraper.py) и Habr
Career (нет API вообще — парсим HTML), у SuperJob есть открытый API:
достаточно бесплатно зарегистрировать приложение на
https://api.superjob.ru/register/ и передавать полученный Secret key в
заголовке X-Api-App-Id. Без него — 403 "Необходимо передать ключ приложения"
(это НЕ блокировка по IP, просто отсутствие ключа).

Схема ответа снята с реального живого запроса 22.09.2026 (не по докам —
официальная документация api.superjob.ru/doc/ сама отдаёт 403 без логина
на superjob.ru, а вторичные источники противоречат друг другу).
"""
import html
import logging
import time
from datetime import datetime, timezone as dt_timezone
from typing import Any

import requests

from apps.jobs.models import Job

from .base import BaseScraper
from .parser import is_frontend_relevant

logger = logging.getLogger(__name__)

# SuperJob отдаёт опыт текстом в поле experience.title — маппим по тексту,
# а не по numeric id (id по факту не задокументирован официально нигде).
EXPERIENCE_MAP = {
    "Без опыта": Job.ExperienceLevel.JUNIOR,
    "От 1 года": Job.ExperienceLevel.JUNIOR,
    "От 3 лет": Job.ExperienceLevel.MIDDLE,
    "От 6 лет": Job.ExperienceLevel.SENIOR,
}

SCHEDULE_MAP = {
    "Полный рабочий день": Job.EmploymentType.FULL_DAY,
    "Неполный рабочий день": Job.EmploymentType.PART_TIME,
}

CURRENCY_MAP = {
    "rub": Job.Currency.RUB,
    "usd": Job.Currency.USD,
    "eur": Job.Currency.EUR,
}


class SuperJobScraper(BaseScraper):
    source_name = "SuperJob"
    source_url = "https://www.superjob.ru"

    api_url = "https://api.superjob.ru/2.0/vacancies/"
    search_keyword = "Frontend"
    per_page = 40  # SuperJob разрешает до 100, берём с запасом на количество страниц
    max_pages = 5
    request_delay_seconds = 0.5

    def __init__(self) -> None:
        from django.conf import settings

        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-Api-App-Id": settings.SUPERJOB_API_KEY,
                "User-Agent": "SearchVakancy/1.0 (+https://github.com/searchvakancy)",
            }
        )

    def fetch_raw_jobs(self) -> list[dict[str, Any]]:
        from django.conf import settings

        if not settings.SUPERJOB_API_KEY:
            logger.warning("SuperJob: SUPERJOB_API_KEY не задан — пропускаю скрейпинг")
            return []

        items: list[dict[str, Any]] = []
        page = 0
        while page < self.max_pages:
            payload = self._fetch_page(page)
            objects = [raw for raw in payload.get("objects", []) if self._is_relevant(raw)]
            items.extend(objects)
            if not payload.get("more") or not payload.get("objects"):
                break
            page += 1
            time.sleep(self.request_delay_seconds)
        return items

    def _fetch_page(self, page: int) -> dict[str, Any]:
        response = self.session.get(
            self.api_url,
            params={"keyword": self.search_keyword, "count": self.per_page, "page": page},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _is_relevant(raw: dict[str, Any]) -> bool:
        if raw.get("is_closed") or raw.get("is_archive"):
            return False
        # У SuperJob ?keyword= ищет по всему тексту вакансии, а не только
        # по названию (проверено вживую: "Старший инженер по исследованиям
        # в области ИИ" и "Software Engineer in Test" попадают в выдачу
        # по "Frontend" — видимо, слово где-то в описании). Параметр srws=1
        # ("искать только в названии", как у некоторых других job-API)
        # эффекта не дал. Поэтому здесь — специально СТРОЖЕ, чем у HH/Habr:
        # смотрим только заголовок, не всё описание.
        return is_frontend_relevant(raw.get("profession", ""))

    def normalize_job(self, raw: dict[str, Any]) -> dict[str, Any]:
        # SuperJob отдаёт текст с неэкранированными HTML-сущностями
        # ("Python &amp; React" вместо "Python & React") — раскодируем.
        title = html.unescape(raw.get("profession", ""))
        description = html.unescape((raw.get("candidat") or "").strip())
        company = html.unescape(raw.get("firm_name") or (raw.get("client") or {}).get("title", ""))

        payment_from = raw.get("payment_from") or None
        payment_to = raw.get("payment_to") or None
        currency = CURRENCY_MAP.get((raw.get("currency") or "").lower(), Job.Currency.RUB)

        experience_title = (raw.get("experience") or {}).get("title", "")
        experience_level = EXPERIENCE_MAP.get(experience_title, "")

        # SuperJob не даёт отдельного флага "удалённо" в структурированном
        # виде (place_of_work у всех проверенных вакансий = "Не имеет
        # значения") — определяем по тексту описания, как и у Habr.
        if "удал" in description.lower():
            employment_type = Job.EmploymentType.REMOTE
        else:
            schedule_title = (raw.get("type_of_work") or {}).get("title", "")
            employment_type = SCHEDULE_MAP.get(schedule_title, "")

        job_type = Job.JobType.INTERNSHIP if "стаж" in title.lower() else ""

        skills = [
            html.unescape(s.get("title", ""))
            for s in raw.get("professionalSkills") or []
            if s.get("title")
        ]

        posted_at: datetime | None = None
        if raw.get("date_published"):
            posted_at = datetime.fromtimestamp(raw["date_published"], tz=dt_timezone.utc)

        return {
            "external_id": str(raw["id"]),
            "title": title,
            "company": company,
            "description": description,
            "salary_from": payment_from,
            "salary_to": payment_to,
            "currency": currency,
            "location": (raw.get("town") or {}).get("title", ""),
            "job_type": job_type,
            "experience_level": experience_level,
            "employment_type": employment_type,
            "required_skills": skills,
            "nice_to_have": [],
            "url": raw.get("link", ""),
            "posted_at": posted_at,
            "is_active": True,
        }
