"""
Скрейпер Staff.am — крупнейший джоб-борд Армении (по независимым оценкам —
~80% локального рынка), публичного API нет: `api.staff.am/robots.txt`
явно запрещает всё (`Disallow: /`). Но сам сайт `staff.am` не трогаем через
api-поддомен — обычные HTML-страницы `staff.am` (тот же Next.js SSR, что
рендерит и сам вызывает этот API на сервере) отдают ровно те же данные
любому посетителю, и `robots.txt` именно этого домена открыт:
`Allow: /`, `Disallow: /*?`, но `Allow: /*?page=` — то есть пагинация явно
разрешена, запрещены только прочие query-параметры. Та же логика, что и
с team.vk.company (см. vk_scraper.py) и Zarplata.ru — не дёргаем закрытый
бэкенд напрямую, только то, что сам сайт открыто отдаёт браузеру.

Next.js встраивает пропсы страницы в `<script id="__NEXT_DATA__">` как
обычный JSON (не экранированный, в отличие от IT-Jobs.uz) — надёжнее
парсить его, чем вёрстку: список карточек (react-native-web, хэшированные
CSS-классы вроде "css-175oi2r" — ломаются от билда к билду) не даёт ни
зарплаты, ни описания, ни навыков, только id/slug/title/company/город/дату
публикации. Полные данные — на detail-странице, тоже через __NEXT_DATA__
(`pageProps.job`), но БЕЗ даты публикации — поэтому normalize объединяет
поля из списка (activated_at) и детальной страницы (всё остальное).

Категория `/en/jobs/software-development` (id=1 в таксономии Staff.am) —
широкая, туда попадает вообще любая разработка (DevOps/Mobile/Backend/
Data), а не только фронтенд (тот же случай, что у Habr с его негерметичным
?specializations=) — поэтому нужен is_frontend_relevant(). НО: проверяем
заголовок + структурированные hard skills (`skills[].type == 2`), а НЕ
заголовок + весь текст описания, как у Habr/VK. Причина — поймано вживую
22.09.2026 на "Senior .Net Engineer" (типичная бэкенд C#/.NET-вакансия):
requirements кончались фразой "knowledge of TypeScript and Angular is an
advantage" — с фильтром по описанию это (и ещё пара похожих) утекло бы в
выдачу только из-за одного упоминания "будет плюсом" в свободном тексте.
Skills у Staff.am — не свободный текст, а теги, расставленные самим
работодателем (hard skills type=2 отдельно от soft skills type=1 вроде
"Teamwork"), поэтому по ним фильтр гораздо точнее. Отдельно от этого —
`FRONTEND_EXCLUDE_KEYWORDS` в parser.py отсеивает всё, где встречается
"fullstack"/"full-stack"/"full stack" (в заголовке или в skills), даже
если рядом есть React/Vue — full-stack позиции в ленту "Frontend" не
нужны, это осознанное решение владельца проекта, а не побочный эффект.

Проверено вживую 22.09.2026: 44 вакансии в категории, все умещаются на
первой странице (totalCount==44, ?page=2 отдаёт 0) — но пагинация всё
равно поддержана на случай роста. Зарплату Staff.am почти никогда не
публикует (salary_from/salary_to стабильно null во всех проверенных
вакансиях) — как и у VK/Habr, это не баг скрейпера.
"""
import json
import logging
import re
import time
from datetime import datetime
from typing import Any

import requests
from django.utils import timezone

from apps.jobs.models import Job

from .base import BaseScraper
from .parser import is_frontend_relevant, strip_html

logger = logging.getLogger(__name__)

NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

GRADE_MAP = {
    "junior": Job.ExperienceLevel.JUNIOR,
    "middle": Job.ExperienceLevel.MIDDLE,
    "senior": Job.ExperienceLevel.SENIOR,
    "lead": Job.ExperienceLevel.LEAD,
}

CURRENCY_MAP = {
    "AMD": Job.Currency.AMD,
    "USD": Job.Currency.USD,
    "EUR": Job.Currency.EUR,
    "RUB": Job.Currency.RUB,
}

# type=2 в skills — технические навыки (JavaScript, AngularJS, REST...);
# type=1 — общие soft skills ("Teamwork", "Analytical skills") — их не
# берём в required_skills, это не то же самое, что стек технологий у
# остальных источников.
HARD_SKILL_TYPE = 2

CATEGORY_CODE = "software-development"


class StaffAmScraper(BaseScraper):
    source_name = "Staff.am"
    source_url = "https://staff.am"

    list_url = f"https://staff.am/en/jobs/{CATEGORY_CODE}"
    max_pages = 3
    request_delay_seconds = 0.5

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "SearchVakancy/1.0 (+https://github.com/searchvakancy)",
                "Accept": "text/html",
            }
        )

    def fetch_raw_jobs(self) -> list[dict[str, Any]]:
        list_items = self._fetch_list_items()

        items: list[dict[str, Any]] = []
        for i, item in enumerate(list_items):
            if i > 0:
                time.sleep(self.request_delay_seconds)
            try:
                detail_html = self._fetch(f"{self.list_url}/{item['slug']}")
            except requests.RequestException:
                logger.exception("StaffAmScraper: failed to fetch vacancy detail %s", item["slug"])
                continue
            raw = self._parse_detail(detail_html, item)
            if raw is not None:
                items.append(raw)
        return items

    def _fetch_list_items(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page in range(1, self.max_pages + 1):
            params = {"page": page} if page > 1 else None
            html = self._fetch(self.list_url, params=params)
            page_items = self._parse_list(html)
            if not page_items:
                break
            items.extend(page_items)
            if page < self.max_pages:
                time.sleep(self.request_delay_seconds)
        return items

    def _fetch(self, url: str, params: dict[str, Any] | None = None) -> str:
        response = self.session.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _next_data(html: str) -> dict[str, Any] | None:
        match = NEXT_DATA_RE.search(html)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    def _parse_list(self, html: str) -> list[dict[str, Any]]:
        data = self._next_data(html)
        if data is None:
            return []
        jobs = data.get("props", {}).get("pageProps", {}).get("jobs") or []

        items: list[dict[str, Any]] = []
        for job in jobs:
            # itemType==0 — промо/баннерные карточки без реальной вакансии.
            if job.get("itemType") != 1:
                continue
            slug = (job.get("slug") or {}).get("en")
            job_id = job.get("id")
            if not slug or job_id is None:
                continue
            items.append(
                {
                    "id": job_id,
                    "slug": slug,
                    "activated_at": (job.get("activated_at") or {}).get("staffam"),
                }
            )
        return items

    def _parse_detail(self, html: str, list_item: dict[str, Any]) -> dict[str, Any] | None:
        data = self._next_data(html)
        if data is None:
            return None
        job = data.get("props", {}).get("pageProps", {}).get("job")
        if not job:
            return None

        country = ((job.get("job_country") or {}).get("title") or {}).get("en", "")
        if country and country != "Armenia":
            return None

        title = ((job.get("title") or {}).get("en") or "").strip()
        if not title:
            return None

        required_skills = [
            (skill.get("title") or {}).get("en", "")
            for skill in job.get("skills") or []
            if skill.get("type") == HARD_SKILL_TYPE
        ]
        required_skills = [s for s in required_skills if s]

        # Проверяем по заголовку + структурированным hard skills, а НЕ по
        # всему тексту описания (в отличие от Habr/VK): описание — свободная
        # проза, где React/TypeScript часто всплывает как "будет плюсом" у
        # чисто бэкенд-вакансий (см. тот же компромисс у SuperJob) — то же
        # самое поймали вживую 22.09.2026 на "Senior .Net Engineer"
        # ("knowledge of typescript and angular is an advantage"). Skills —
        # куратор самого работодателя, не случайное упоминание в тексте.
        if not is_frontend_relevant(title, " ".join(required_skills)):
            return None

        company = ((job.get("companiesStruct") or {}).get("title") or {}).get("en", "")
        location = ((job.get("job_city") or {}).get("title") or {}).get("en", "")

        currency = CURRENCY_MAP.get(job.get("salary_currency", ""), Job.Currency.AMD)
        level_en = ((job.get("job_candidate_level") or {}).get("title") or {}).get("en", "")
        experience_level = GRADE_MAP.get(level_en.lower(), "")

        job_term_en = ((job.get("job_term") or {}).get("title") or {}).get("en", "")
        job_type = Job.JobType.FULL_TIME if job_term_en == "Permanent" else ""

        job_type_en = ((job.get("job_type") or {}).get("title") or {}).get("en", "")
        if job.get("is_remote"):
            employment_type = Job.EmploymentType.REMOTE
        elif "part" in job_type_en.lower():
            employment_type = Job.EmploymentType.PART_TIME
        else:
            employment_type = Job.EmploymentType.FULL_DAY

        description = self._build_description(job)

        return {
            "external_id": str(list_item["id"]),
            "title": title,
            "company": company,
            "description": description,
            "salary_from": job.get("salary_from"),
            "salary_to": job.get("salary_to"),
            "currency": currency,
            "location": location,
            "job_type": job_type,
            "experience_level": experience_level,
            "employment_type": employment_type,
            "required_skills": required_skills,
            "nice_to_have": [],
            "url": f"{self.list_url}/{list_item['slug']}",
            "posted_at": _parse_datetime(list_item.get("activated_at")),
            "is_active": True,
        }

    @staticmethod
    def _build_description(job: dict[str, Any]) -> str:
        parts = [
            (job.get("description") or {}).get("en", ""),
            (job.get("responsibilities") or {}).get("en", ""),
            (job.get("required_qualifications") or {}).get("en", ""),
        ]
        return "\n\n".join(strip_html(p) for p in parts if p).strip()

    def normalize_job(self, raw: dict[str, Any]) -> dict[str, Any]:
        # _parse_detail уже собрал финальный словарь под поля Job.
        return raw


def _parse_datetime(value: str | None) -> datetime | None:
    """activated_at приходит как "YYYY-MM-DD HH:MM:SS" (время staff.am,
    без явного часового пояса) — интерпретируем в таймзоне проекта, как и
    даты VK (см. vk_scraper.py)."""
    if not value:
        return None
    try:
        naive = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return timezone.make_aware(naive)
