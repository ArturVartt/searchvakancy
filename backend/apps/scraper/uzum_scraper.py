"""
Скрейпер Uzum (people.uzum.com) — карьерный портал крупнейшей e-commerce/
fintech-экосистемы Узбекистана (Uzum Market, Uzum Bank, Uzum Nasiya, Uzum
Tezkor и др.), публичного API нет. Добавлен по прямой просьбе владельца
проекта поискать "бигтехи" Узбекистана — даже несмотря на то, что на
момент проверки (23.09.2026) среди всех 64 открытых вакансий не было ни
одной фронтенд-позиции (сплошь Java/Go/QA/Data/DevOps): источник
технически надёжный и сам подхватит фронтенд-вакансии, когда они
появятся — Uzum активно растёт, а сравнение с другими "бигтехами"
Узбекистана (Payme — чистый клиентский Angular без единой ссылки в HTML,
Anor Bank — `robots.txt` блокирует пагинацию) показало, что Uzum
уникально хорошо скрейпится среди всех проверенных.

`robots.txt` открытый (`Allow: /`, запрещены только `/api/` и
`/monitoring/`). Список вакансий (`/career/ru/vacancies`) фильтруется на
клиенте (JS) — простой GET отдаёт только ~15 последних вакансий
независимо от query-параметров (`?query=frontend` не влияет на выдачу).
Вместо этого используем `sitemap.xml`, который перечисляет ВСЕ текущие
открытые вакансии — и на `ru`, и на `uz` (дубли одних и тех же ID на
двух языках), берём только `/career/ru/vacancies/`.

Обычный серверно-рендеренный HTML (CSS-modules с хэшированными классами,
без __NEXT_DATA__/__NUXT__ — хрупко к вёрстке, как и Habr). Заголовок —
из `<title>` (до " | Uzum People", самый надёжный источник, не завязан
на конкретный CSS-класс). Теги — департамент + бренд-компания (последний
тег), "Город • Формат • Опыт" — в отдельном `<p>` через буллет. Кнопка
"Откликнуться" — JS-виджет (`<button>`, не `<a>`), прямого apply-URL нет
— `url` ведёт на саму страницу вакансии.
"""
import logging
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

from apps.jobs.models import Job

from .base import BaseScraper
from .parser import is_frontend_relevant, strip_html

logger = logging.getLogger(__name__)

FORMAT_MAP = {
    "удалённая работа": Job.EmploymentType.REMOTE,
    "офис": Job.EmploymentType.FULL_DAY,
    "гибридный": Job.EmploymentType.FULL_DAY,
}

REQUEST_DELAY_SECONDS = 0.5


class UzumScraper(BaseScraper):
    source_name = "Uzum"
    source_url = "https://people.uzum.com/career/ru/vacancies"

    sitemap_url = "https://people.uzum.com/sitemap.xml"
    vacancy_path_prefix = "/career/ru/vacancies/"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "SearchVakancy/1.0 (+https://github.com/searchvakancy)",
                "Accept": "text/html",
            }
        )

    def fetch_raw_jobs(self) -> list[dict[str, Any]]:
        urls = self._discover_vacancy_urls()

        items: list[dict[str, Any]] = []
        for i, url in enumerate(urls):
            if i > 0:
                time.sleep(REQUEST_DELAY_SECONDS)
            try:
                html = self._fetch(url)
            except requests.RequestException:
                logger.exception("UzumScraper: failed to fetch vacancy detail %s", url)
                continue
            raw = self._parse_detail(html, url)
            if raw is not None:
                items.append(raw)
        return items

    def _discover_vacancy_urls(self) -> list[str]:
        sitemap_xml = self._fetch(self.sitemap_url)
        # Простой regex вместо XML-парсера — sitemap.xml плоский,
        # <loc>...</loc> без вложенности, парсер тут избыточен.
        locs = re.findall(r"<loc>(.*?)</loc>", sitemap_xml)
        urls: list[str] = []
        seen: set[str] = set()
        for loc in locs:
            if self.vacancy_path_prefix not in loc:
                continue
            if loc not in seen:
                seen.add(loc)
                urls.append(loc)
        return urls

    def _fetch(self, url: str) -> str:
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        return response.text

    def _parse_detail(self, html: str, url: str) -> dict[str, Any] | None:
        match = re.search(r"/vacancies/(\d+)", url)
        if not match:
            return None
        external_id = match.group(1)

        soup = BeautifulSoup(html, "lxml")

        title = ""
        if soup.title:
            title = soup.title.get_text().split(" | ")[0].strip()
        if not title:
            return None

        description = self._extract_description(soup)
        if not is_frontend_relevant(title, description):
            return None

        tags = [t.get_text(strip=True) for t in soup.select(".vacancy-hero_tags__6L6HB .tag-list_tag__XvSQL")]
        company = tags[-1] if tags else "Uzum"

        location, employment_type, experience_level = self._parse_meta(soup)

        return {
            "external_id": external_id,
            "title": title,
            "company": company,
            "description": description,
            "salary_from": None,
            "salary_to": None,
            "currency": Job.Currency.UZS,
            "location": location,
            "job_type": "",
            "experience_level": experience_level,
            "employment_type": employment_type,
            "required_skills": [],
            "nice_to_have": [],
            "url": url,
            "posted_at": None,
            "is_active": True,
        }

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str:
        container = soup.select_one(".vacancy-content_container__5shzh")
        if container is None:
            return ""
        # Кнопки "Откликнуться"/"Поделиться" и т.п. — не часть описания.
        actions = container.select_one(".vacancy-content_actions__ZCJ0Z")
        if actions is not None:
            actions.decompose()
        return strip_html(str(container))

    @staticmethod
    def _parse_meta(soup: BeautifulSoup) -> tuple[str, str, str]:
        desc_el = soup.select_one(".vacancy-hero_description__b1W06")
        if desc_el is None:
            return "", "", ""
        parts = [p.strip() for p in desc_el.get_text(strip=True).split("•")]

        location = parts[0] if len(parts) > 0 else ""
        employment_type = FORMAT_MAP.get(parts[1].lower(), "") if len(parts) > 1 else ""
        experience_level = _parse_experience(parts[2]) if len(parts) > 2 else ""

        return location, employment_type, experience_level

    def normalize_job(self, raw: dict[str, Any]) -> dict[str, Any]:
        # _parse_detail уже собрал финальный словарь под поля Job.
        return raw


def _parse_experience(text: str) -> str:
    """
    "Без опыта" / "От 1 года" / "От 3 лет" и т.п. — та же бакетизация по
    числу лет, что и в hh_scraper.py/zarplata_scraper.py
    (noExperience/between1And3 -> JUNIOR, between3And6 -> MIDDLE,
    moreThan6 -> SENIOR), просто здесь число не enum, а свободный текст.
    """
    numbers = re.findall(r"\d+", text)
    years = int(numbers[0]) if numbers else 0
    if years >= 6:
        return Job.ExperienceLevel.SENIOR
    if years >= 3:
        return Job.ExperienceLevel.MIDDLE
    return Job.ExperienceLevel.JUNIOR
