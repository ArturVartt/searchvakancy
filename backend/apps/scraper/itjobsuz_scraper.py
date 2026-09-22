"""
Скрейпер IT-Jobs.uz (it-jobs.uz) — площадка вакансий по Узбекистану,
публичного API нет. Next.js-приложение, но данные не догружаются JS'ом —
они зашиты сервером прямо в HTML как inline JSON (React Server
Components flight-payload), поэтому обычный GET + разбор строк достаточен,
headless-браузер не нужен (в отличие от GetMatch, где это не сработало бы).

Внутри HTML это JSON, ещё раз завёрнутый в JS-строку — кавычки
экранированы обратным слэшем (\\"title\\":\\"..." вместо "title":"...").
Обычный json.loads тут не поможет (это не самостоятельный JSON-документ,
а часть куда большей RSC-структуры) — вытаскиваем поля регэкспами по
блокам, найденным по маркеру `\\"job\\":{`.

Проверено вживую 22.09.2026: `robots.txt` разрешает всё, кроме /api/ и
/admin/; сейчас на сайте 16 вакансий всего по Узбекистану, 6 из них —
категория "Фронтенд". Ни explicit ?category=, ни пагинация не нужны —
сайт отдаёт единым списком всё активное сразу (полей hasMore/totalCount
в пейлоаде нет).
"""
import logging
import re
from datetime import datetime
from typing import Any

import requests
from django.utils.dateparse import parse_datetime

from apps.jobs.models import Job

from .base import BaseScraper
from .parser import is_frontend_relevant

logger = logging.getLogger(__name__)

EXPERIENCE_MAP = {
    "JUNIOR": Job.ExperienceLevel.JUNIOR,
    "MIDDLE": Job.ExperienceLevel.MIDDLE,
    "MID": Job.ExperienceLevel.MIDDLE,
    "SENIOR": Job.ExperienceLevel.SENIOR,
    "LEAD": Job.ExperienceLevel.LEAD,
    # "ANY"/прочее -> "" (неизвестно), см. .get() с default ниже
}

CURRENCY_MAP = {
    "UZS": Job.Currency.UZS,
    "USD": Job.Currency.USD,
    "EUR": Job.Currency.EUR,
    "RUB": Job.Currency.RUB,
}

# В реальном HTML экранирование одинарное: \"name\":\"значение\" — ровно
# один буквальный backslash перед каждой кавычкой (см. докстринг модуля).
# Строим паттерны через re.escape() на ОБЫЧНЫХ (не raw) строках, где "\\"
# однозначно значит один backslash — так не приходится вручную считать
# слэши в raw-литералах (перепутать одинарный/двойной там легко, и в
# первой версии этого файла именно так и вышло: _JOB_BLOCK_SPLIT не
# матчился вообще ни разу — re.split() возвращал один сплошной блок).
_JOB_BLOCK_MARKER = '\\"job\\":{'


def _field_regex(name: str, value_pattern: str = r"[^\\]*") -> re.Pattern:
    prefix = re.escape('\\"' + name + '\\":\\"')
    suffix = re.escape('\\"')
    return re.compile(prefix + "(" + value_pattern + ")" + suffix)


# Поля внутри блока — все в одном экранированном JSON-фрагменте, без
# гарантии порядка, поэтому ищем каждое по отдельности через .search().
_FIELD_RE = {
    "id": _field_regex("id"),
    "slug": _field_regex("slug"),
    "title": _field_regex("title"),
    "companyName": _field_regex("companyName"),
    "location": _field_regex("location"),
    "workType": _field_regex("workType"),
    "experienceLevel": _field_regex("experienceLevel"),
    "salaryMin": re.compile(re.escape('\\"salaryMin\\":') + r"(null|\d+)"),
    "salaryMax": re.compile(re.escape('\\"salaryMax\\":') + r"(null|\d+)"),
    "salaryCurrency": _field_regex("salaryCurrency"),
    "description": _field_regex("description"),
    "categoryName": _field_regex("categoryName"),
    "publishedAt": _field_regex("publishedAt"),
}


class ItJobsUzScraper(BaseScraper):
    source_name = "IT-Jobs.uz"
    source_url = "https://it-jobs.uz"

    list_url = "https://it-jobs.uz/ru"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "SearchVakancy/1.0 (+https://github.com/searchvakancy)",
                "Accept": "text/html",
            }
        )

    def fetch_raw_jobs(self) -> list[dict[str, Any]]:
        html = self._fetch_page()

        items: list[dict[str, Any]] = []
        # Литеральное разбиение, не regex — маркер фиксированная строка,
        # re.split() тут не нужен и раньше именно это было источником бага.
        for block in html.split(_JOB_BLOCK_MARKER)[1:]:
            raw = self._extract_fields(block[:4000])  # с запасом на самое длинное описание
            if raw is not None and self._is_relevant(raw):
                items.append(raw)
        return items

    def _fetch_page(self) -> str:
        response = self.session.get(self.list_url, timeout=10)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _extract_fields(block: str) -> dict[str, str] | None:
        raw: dict[str, str] = {}
        for key, pattern in _FIELD_RE.items():
            match = pattern.search(block)
            if match:
                raw[key] = match.group(1)
        if "id" not in raw or "title" not in raw:
            return None
        return raw

    @staticmethod
    def _is_relevant(raw: dict[str, str]) -> bool:
        return raw.get("categoryName") == "Фронтенд" or is_frontend_relevant(
            raw.get("title", ""), raw.get("description", "")
        )

    def normalize_job(self, raw: dict[str, Any]) -> dict[str, Any]:
        salary_from = _parse_int_or_none(raw.get("salaryMin"))
        salary_to = _parse_int_or_none(raw.get("salaryMax"))
        currency = CURRENCY_MAP.get(raw.get("salaryCurrency", ""), Job.Currency.UZS)

        experience_level = EXPERIENCE_MAP.get(raw.get("experienceLevel", ""), "")
        employment_type = (
            Job.EmploymentType.REMOTE if raw.get("workType") == "REMOTE" else Job.EmploymentType.FULL_DAY
        )

        # Экранированные \n / \" внутри самой строки описания декодируем
        # вручную — это фрагмент JS-строки, не полноценный JSON.
        description = (raw.get("description") or "").replace("\\n", "\n").replace('\\"', '"')

        posted_at: datetime | None = None
        if raw.get("publishedAt"):
            posted_at = parse_datetime(raw["publishedAt"])

        slug = raw.get("slug", "")

        return {
            "external_id": raw["id"],
            "title": raw.get("title", ""),
            "company": raw.get("companyName", ""),
            "description": description,
            "salary_from": salary_from,
            "salary_to": salary_to,
            "currency": currency,
            "location": raw.get("location") or "Узбекистан",
            "job_type": "",
            "experience_level": experience_level,
            "employment_type": employment_type,
            "required_skills": [],
            "nice_to_have": [],
            "url": f"https://it-jobs.uz/ru/jobs/{slug}" if slug else self.list_url,
            "posted_at": posted_at,
            "is_active": True,
        }


def _parse_int_or_none(value: str | None) -> int | None:
    if not value or value == "null":
        return None
    return int(value)
