"""
Скрейпер HH.uz — узбекская площадка той же платформы HH Group, что и
HH.ru/Zarplata.ru (см. zarplata_scraper.py): разметка идентична
("data-qa"-атрибуты, `<data value="...">` для зарплаты/опыта). Проверено
вживую 22.09.2026: `GET /search/vacancy?text=frontend&area=97` отдаёт 200 и
20 настоящих вакансий от реальных узбекских работодателей (не 403, как у
основного hh.ru после апрельского закрытия API).

Между запросами страниц — случайные паузы (`HUMAN_DELAY_RANGE`), а не
фиксированная 1 секунда, как у остальных скрейперов.
"""
import logging
import random
import time
from typing import Any

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from apps.jobs.models import Job

from .base import BaseScraper
from .parser import is_frontend_relevant

logger = logging.getLogger(__name__)

# Тот же enum, что в zarplata_scraper.py/hh_scraper.py.
EXPERIENCE_MAP = {
    "noExperience": Job.ExperienceLevel.JUNIOR,
    "between1And3": Job.ExperienceLevel.JUNIOR,
    "between3And6": Job.ExperienceLevel.MIDDLE,
    "moreThan6": Job.ExperienceLevel.SENIOR,
}

CURRENCY_MAP = {
    "RUB": Job.Currency.RUB,
    "USD": Job.Currency.USD,
    "EUR": Job.Currency.EUR,
    "UZS": Job.Currency.UZS,
}

# "Человеческие" паузы между запросами страниц — см. докстринг модуля.
HUMAN_DELAY_RANGE = (2.5, 5.5)


class HHUzScraper(BaseScraper):
    source_name = "HH.uz"
    source_url = "https://hh.uz"

    search_url = "https://hh.uz/search/vacancy"
    search_keyword = "Frontend"
    area = 97  # Узбекистан целиком (проверено вживую 22.09.2026)
    max_pages = 5

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "SearchVakancy/1.0 (+https://github.com/searchvakancy)",
                "Accept": "text/html",
            }
        )

    def fetch_raw_jobs(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page in range(self.max_pages):
            html = self._fetch_page(page)
            cards = self._parse_cards(html)
            if not cards:
                break
            items.extend(cards)
            if page < self.max_pages - 1:
                time.sleep(random.uniform(*HUMAN_DELAY_RANGE))
        return items

    def _fetch_page(self, page: int) -> str:
        params: dict[str, Any] = {
            "text": self.search_keyword,
            "search_field": "name",
            "area": self.area,
            "page": page,
        }
        response = self.session.get(self.search_url, params=params, timeout=10)
        response.raise_for_status()
        return response.text

    def _parse_cards(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        parsed = (self._parse_one_card(card) for card in soup.select('[data-qa="vacancy-serp__vacancy"]'))
        return [item for item in parsed if item is not None]

    def _parse_one_card(self, card: Tag) -> dict[str, Any] | None:
        title_el = card.select_one('[data-qa="serp-item__title-text"]')
        link_el = card.select_one('[data-qa="serp-item__title"]')
        if title_el is None or link_el is None:
            return None
        title = title_el.get_text(strip=True)
        href = link_el.get("href", "")

        skills_hint = card.get_text(" ", strip=True)
        if not is_frontend_relevant(title, skills_hint):
            return None

        external_id = self._external_id(href)
        if external_id is None:
            return None

        company_el = card.select_one('[data-qa="vacancy-serp__vacancy-employer-text"]')
        location_el = card.select_one('[data-qa="vacancy-serp__vacancy-address"]')

        salary_from, salary_to, currency = self._parse_salary(card)
        experience_level = self._parse_experience(card)
        employment_type = (
            Job.EmploymentType.REMOTE if card.select_one('[data-qa="vacancy-label-work-schedule-remote"]') else ""
        )

        description_parts = [
            el.get_text(" ", strip=True)
            for el in card.select(
                '[data-qa="vacancy-serp__vacancy_snippet_requirement"], '
                '[data-qa="vacancy-serp__vacancy_snippet_responsibility"]'
            )
        ]

        return {
            "external_id": external_id,
            "title": title,
            "company": company_el.get_text(strip=True) if company_el else "",
            "description": " ".join(description_parts),
            "salary_from": salary_from,
            "salary_to": salary_to,
            "currency": currency,
            "location": location_el.get_text(strip=True) if location_el else "",
            "job_type": "",
            "experience_level": experience_level,
            "employment_type": employment_type,
            "required_skills": [],
            "nice_to_have": [],
            "url": href if href.startswith("http") else f"https://hh.uz{href}",
            "posted_at": None,  # список не отдаёт дату публикации отдельным полем
            "is_active": True,
        }

    @staticmethod
    def _external_id(href: str) -> str | None:
        # href вида "https://hh.uz/vacancy/137527751?query=..."
        path = href.split("?", 1)[0]
        vacancy_id = path.rsplit("/", 1)[-1]
        return vacancy_id if vacancy_id.isdigit() else None

    @staticmethod
    def _parse_salary(card: Tag) -> tuple[int | None, int | None, str]:
        """См. ту же логику в zarplata_scraper.py — идентичная разметка."""
        amounts: list[int] = []
        currency = Job.Currency.UZS
        for data_el in card.find_all("data"):
            value = data_el.get("value", "")
            if value in CURRENCY_MAP:
                currency = CURRENCY_MAP[value]
            elif value.isdigit():
                amounts.append(int(value))
        if len(amounts) >= 2:
            return amounts[0], amounts[1], currency
        if len(amounts) == 1:
            return amounts[0], None, currency
        return None, None, currency

    @staticmethod
    def _parse_experience(card: Tag) -> str:
        for key, level in EXPERIENCE_MAP.items():
            if card.select_one(f'[data-qa="vacancy-serp__vacancy-work-experience-{key}"]'):
                return level
        return ""

    def normalize_job(self, raw: dict[str, Any]) -> dict[str, Any]:
        # _parse_one_card уже собрал финальный словарь под поля Job.
        return raw
