"""
Скрейпер VK (team.vk.company) — карьерный сайт холдинга VK (ВКонтакте, OK,
Dzen, Mail.ru, RuStore, VK Play и др.), публичного API нет.

Важно отличать от vk.com/jobs, который разбирался раньше (см. README,
раздел "VK Jobs — не реализован") — это была карьерная SPA-страница самого
ВКонтакте с приватным API (method/jobs.vacancies) и вшитым в HTML
client_secret. team.vk.company — совсем другой, официальный корпоративный
сайт вакансий всего холдинга: обычный серверно-рендеренный HTML без всякой
JS-магии, `robots.txt` запрещает только /load_more/ и /render_partial/
(внутренние AJAX-эндпоинты для догрузки списка — сюда мы и не ходим).

Список вакансий (`?specialty=287` — id специализации "Frontend" в
собственной таксономии VK) не отдаёт зарплату/описание/теги — только
заголовок, команду и город. Полные данные — на странице вакансии, которая
размечена как настоящий schema.org JobPosting (`itemprop="title"`,
`hiringOrganization`, `addressLocality`, `description`, `datePosted`) —
поэтому normalize_job почти не нужен, вся нормализация уже в fetch.
Формат работы/уровень/график — отдельные `.vacancy-tag` блоки без
schema.org-разметки, каждый подписан своим `h4.vacancy-title`
("Формат работы" / "Уровень" / "График работы").

Зарплату VK, как и большинство крупных компаний в этом проекте (VK, Habr),
публично не показывает — salary_from/salary_to всегда None, это не баг
парсинга.

Проверено вживую 22.09.2026: сейчас на сайте всего 3-4 фронтенд-вакансии
(маленький, но настоящий отдельный источник, не то же самое, что HH/Zarplata) —
поэтому N+1 запросов на детальные страницы приемлемо, в отличие от Habr,
где вакансий на порядки больше.
"""
import logging
import re
import time
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup
from django.utils import timezone

from apps.jobs.models import Job

from .base import BaseScraper
from .parser import is_frontend_relevant

logger = logging.getLogger(__name__)

# "Уровень" на detail-странице уже приходит строчными буквами и почти
# совпадает с Job.ExperienceLevel.value — но матчим явным словарём, а не
# полагаемся на совпадение, чтобы не сломаться молча, если VK когда-нибудь
# добавит свой grade вроде "стажёр" или "principal".
GRADE_MAP = {
    "junior": Job.ExperienceLevel.JUNIOR,
    "middle": Job.ExperienceLevel.MIDDLE,
    "senior": Job.ExperienceLevel.SENIOR,
    "lead": Job.ExperienceLevel.LEAD,
}

FRONTEND_SPECIALTY_ID = 287


class VKScraper(BaseScraper):
    source_name = "VK"
    source_url = "https://team.vk.company"

    list_url = "https://team.vk.company/vacancy/"
    request_delay_seconds = 1.0

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "SearchVakancy/1.0 (+https://github.com/searchvakancy)",
                "Accept": "text/html",
            }
        )

    def fetch_raw_jobs(self) -> list[dict[str, Any]]:
        list_html = self._fetch(self.list_url, params={"specialty": FRONTEND_SPECIALTY_ID})
        urls = self._parse_list(list_html)

        items: list[dict[str, Any]] = []
        for i, url in enumerate(urls):
            if i > 0:
                time.sleep(self.request_delay_seconds)
            try:
                detail_html = self._fetch(url)
            except requests.RequestException:
                logger.exception("VKScraper: failed to fetch vacancy detail %s", url)
                continue
            raw = self._parse_detail(detail_html, url)
            if raw is not None:
                items.append(raw)
        return items

    def _fetch(self, url: str, params: dict[str, Any] | None = None) -> str:
        response = self.session.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _parse_list(html: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        urls: list[str] = []
        seen: set[str] = set()
        for a in soup.select("a.vacancy_vacancyItem__jrNqL"):
            href = a.get("href", "")
            if not re.match(r"^/vacancy/\d+/?$", href):
                continue
            url = f"https://team.vk.company{href}"
            if url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    def _parse_detail(self, html: str, url: str) -> dict[str, Any] | None:
        soup = BeautifulSoup(html, "lxml")
        posting = soup.select_one('[itemtype="http://schema.org/JobPosting"]') or soup.select_one(
            '[itemtype="https://schema.org/JobPosting"]'
        )
        if posting is None:
            return None

        match = re.search(r"/vacancy/(\d+)", url)
        if not match:
            return None
        external_id = match.group(1)

        title_el = posting.select_one('[itemprop="title"]')
        title = title_el.get("content") or title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None

        org_el = posting.select_one('[itemprop="name"]')
        company = (org_el.get("content") if org_el else "") or ""

        locality_el = posting.select_one('[itemprop="addressLocality"]')
        location = (locality_el.get("content") if locality_el else "") or ""

        desc_el = posting.select_one('[itemprop="description"]')
        description = desc_el.get_text("\n", strip=True) if desc_el else ""

        # ?specialty=287 — собственная таксономия VK, в целом надёжная, но
        # is_frontend_relevant() — та же подстраховка "второй проверкой",
        # что и у Habr/IT-Jobs.uz, а не дублирование на всякий случай.
        if not is_frontend_relevant(title, description):
            return None

        date_el = posting.select_one('[itemprop="datePosted"]')
        posted_at = _parse_date(date_el.get("content")) if date_el else None

        experience_level = self._extract_level(soup)
        employment_type = self._extract_employment_type(soup)

        return {
            "external_id": external_id,
            "title": title,
            "company": company,
            "description": description,
            "salary_from": None,
            "salary_to": None,
            "currency": Job.Currency.RUB,
            "location": location,
            "job_type": "",
            "experience_level": experience_level,
            "employment_type": employment_type,
            "required_skills": [],
            "nice_to_have": [],
            "url": url,
            "posted_at": posted_at,
            "is_active": True,
        }

    @staticmethod
    def _tag_group(soup: BeautifulSoup, label: str) -> list[str]:
        """
        Метаблоки на странице вакансии не размечены schema.org — только
        подписью в h4.vacancy-title ("Формат работы"/"Уровень"/"График
        работы") и соседним div со списком .vacancy-tag. См. докстринг
        модуля.
        """
        for h4 in soup.select("h4.vacancy-title"):
            if h4.get_text(strip=True) != label:
                continue
            group = h4.parent.find_next_sibling("div") if h4.parent else None
            if group is None:
                return []
            return [t.get_text(strip=True) for t in group.select(".vacancy-tag")]
        return []

    def _extract_level(self, soup: BeautifulSoup) -> str:
        for value in self._tag_group(soup, "Уровень"):
            level = GRADE_MAP.get(value.lower())
            if level:
                return level
        return ""

    def _extract_employment_type(self, soup: BeautifulSoup) -> str:
        schedule = [s.lower() for s in self._tag_group(soup, "График работы")]
        if any("частич" in s for s in schedule):
            return Job.EmploymentType.PART_TIME

        work_format = self._tag_group(soup, "Формат работы")
        # Формат "только дистанционно" (без опций офиса/гибрида) — реально
        # удалённая вакансия. Если среди опций есть офис/гибрид, считаем
        # обычным полным днём, как и у остальных скрейперов проекта.
        if work_format and all("дистанц" in w.lower() for w in work_format):
            return Job.EmploymentType.REMOTE
        return Job.EmploymentType.FULL_DAY

    def normalize_job(self, raw: dict[str, Any]) -> dict[str, Any]:
        # _parse_detail уже собрал финальный словарь под поля Job.
        return raw


def _parse_date(value: str | None) -> datetime | None:
    """datePosted приходит как чистая дата "YYYY-MM-DD", без времени."""
    if not value:
        return None
    try:
        naive = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None
    return timezone.make_aware(naive)
