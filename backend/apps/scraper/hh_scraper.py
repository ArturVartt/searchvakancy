"""
Скрейпер HH.ru через официальный публичный API (api.hh.ru/vacancies) —
без HTML-парсинга и авторизации. Документация: https://api.hh.ru/openapi/

Важно: HH.ru требует адекватный заголовок User-Agent (формат
"Приложение/Версия (контакт)") и банит через DDoS-Guard подозрительные
дата-центровые IP — если видите {"errors":[{"type":"forbidden"}]},
это блокировка на их стороне, а не баг скрейпера; попробуйте с другого IP
или добавьте прокси.
"""
import logging
import time
from datetime import datetime
from typing import Any

import requests
from django.utils.dateparse import parse_datetime

from apps.jobs.models import Job

from .base import BaseScraper
from .parser import strip_html

logger = logging.getLogger(__name__)

# https://api.hh.ru/openapi/redoc#tag/Obshie-spravochniki/operation/get-areas -> 113 = Россия
AREA_RUSSIA = 113

# HH-специфичные словари -> наши choices. Соответствие приблизительное
# (у HH нет прямого аналога "тип занятости" в терминах плана), но
# достаточно для сортировки/фильтрации на списке вакансий.
EMPLOYMENT_TO_JOB_TYPE = {
    "full": Job.JobType.FULL_TIME,
    "project": Job.JobType.CONTRACT,
    "probation": Job.JobType.INTERNSHIP,
    "volunteer": Job.JobType.FREELANCE,
}
SCHEDULE_TO_EMPLOYMENT_TYPE = {
    "remote": Job.EmploymentType.REMOTE,
    "fullDay": Job.EmploymentType.FULL_DAY,
    "flexible": Job.EmploymentType.FULL_DAY,
    "shift": Job.EmploymentType.FULL_DAY,
}
EXPERIENCE_TO_LEVEL = {
    "noExperience": Job.ExperienceLevel.JUNIOR,
    "between1And3": Job.ExperienceLevel.JUNIOR,
    "between3And6": Job.ExperienceLevel.MIDDLE,
    "moreThan6": Job.ExperienceLevel.SENIOR,
}
CURRENCY_MAP = {"RUR": Job.Currency.RUB, "RUB": Job.Currency.RUB, "USD": Job.Currency.USD, "EUR": Job.Currency.EUR}


class HHScraper(BaseScraper):
    source_name = "HH.ru"
    source_url = "https://hh.ru"

    api_base_url = "https://api.hh.ru/vacancies"
    search_text = "Frontend OR Фронтенд OR Front-end"
    per_page = 50
    max_pages = 5  # per_page * max_pages = верхняя граница вакансий за один прогон
    request_delay_seconds = 0.34  # HH просит не чаще ~3 запросов/сек

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                # HH банит дефолтные/пустые User-Agent — обязателен формат "App/Version (contact)"
                "User-Agent": "SearchVakancy/1.0 (+https://github.com/searchvakancy)",
                "Accept": "application/json",
            }
        )

    def fetch_raw_jobs(self) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        page = 0
        total_pages = 1

        while page < total_pages and page < self.max_pages:
            response = self._get_with_retries(
                params={
                    "text": self.search_text,
                    "search_field": "name",
                    "area": AREA_RUSSIA,
                    "per_page": self.per_page,
                    "page": page,
                }
            )
            payload = response.json()
            jobs.extend(payload.get("items", []))
            total_pages = payload.get("pages", 1)
            page += 1
            if page < total_pages and page < self.max_pages:
                time.sleep(self.request_delay_seconds)

        return jobs

    def _get_with_retries(self, params: dict[str, Any], retries: int = 3) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                response = self.session.get(self.api_base_url, params=params, timeout=10)
                if response.status_code in (429, 503):
                    wait = 2**attempt
                    logger.warning(
                        "HH API вернул %s, жду %sс (попытка %s/%s)",
                        response.status_code,
                        wait,
                        attempt + 1,
                        retries,
                    )
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(2**attempt)
        assert last_exc is not None
        raise last_exc

    def normalize_job(self, raw: dict[str, Any]) -> dict[str, Any]:
        salary = raw.get("salary") or {}
        employer = raw.get("employer") or {}
        area = raw.get("area") or {}
        snippet = raw.get("snippet") or {}
        schedule = raw.get("schedule") or {}
        employment = raw.get("employment") or {}
        experience = raw.get("experience") or {}

        description = " ".join(
            filter(
                None,
                [
                    strip_html(snippet.get("requirement")),
                    strip_html(snippet.get("responsibility")),
                ],
            )
        )

        posted_at: datetime | None = None
        if raw.get("published_at"):
            posted_at = parse_datetime(raw["published_at"])

        return {
            "external_id": str(raw["id"]),
            "title": raw.get("name", ""),
            "company": employer.get("name", ""),
            "description": description,
            "salary_from": salary.get("from"),
            "salary_to": salary.get("to"),
            "currency": CURRENCY_MAP.get(salary.get("currency"), Job.Currency.RUB),
            "location": area.get("name", ""),
            "job_type": EMPLOYMENT_TO_JOB_TYPE.get(employment.get("id"), ""),
            "experience_level": EXPERIENCE_TO_LEVEL.get(experience.get("id"), ""),
            "employment_type": SCHEDULE_TO_EMPLOYMENT_TYPE.get(schedule.get("id"), ""),
            # HH отдаёт key_skills только в деталях вакансии (GET /vacancies/{id}),
            # не в списке поиска — дотягивать по одному было бы N+1 запросов.
            # Оставляем пустым в PoC; можно добавить опциональное обогащение позже.
            "required_skills": [],
            "nice_to_have": [],
            "url": raw.get("alternate_url", ""),
            "posted_at": posted_at,
            "is_active": True,
        }
