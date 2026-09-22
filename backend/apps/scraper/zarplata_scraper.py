"""
Скрейпер Zarplata.ru — парсим серверно-рендеренный HTML списка вакансий
(BeautifulSoup), публичного API нет (сам API есть — но это буквально
внутренний api.hh.ru, тот самый закрытый в апреле 2026 публичный API HH.ru;
Zarplata.ru — тот же движок/база HH Group, просто отдельный бренд/домен).

Важно (проверено вживую 22.09.2026): Zarplata.ru рендерит страницы своим
Node/React SSR-бэкендом, который сам ходит в api.hh.ru с внутренними
правами и отдаёт готовый HTML любому посетителю — это подтверждено прямо
в её собственном JS-конфиге на странице (window.globalVars.apiHost ==
"https://api.hh.ru"). Технически это не то же самое действие, что прямой
запрос к api.hh.ru (сюда HH-ключ не нужен), но семантически — тот же
источник данных с другой стороны. Разметка ("data-qa"-атрибуты, enum
опыта noExperience/between1And3/...) идентична HH.ru.

`robots.txt` (https://zarplata.ru/robots.txt) явно разрешает
/vacancies/*?page= и отдельно запрещает только /vacancy/* (детальные
страницы) — сюда мы и не ходим, используем только список.
"""
import logging
import time
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from django.utils.dateparse import parse_datetime

from apps.jobs.models import Job

from .base import BaseScraper
from .parser import is_frontend_relevant

logger = logging.getLogger(__name__)

# Тот же enum, что в hh_scraper.py — Zarplata.ru рендерит его буквально
# в data-qa="vacancy-serp__vacancy-work-experience-<id>".
EXPERIENCE_MAP = {
    "noExperience": Job.ExperienceLevel.JUNIOR,
    "between1And3": Job.ExperienceLevel.JUNIOR,
    "between3And6": Job.ExperienceLevel.MIDDLE,
    "moreThan6": Job.ExperienceLevel.SENIOR,
}

CURRENCY_MAP = {"RUB": Job.Currency.RUB, "USD": Job.Currency.USD, "EUR": Job.Currency.EUR}


class ZarplataScraper(BaseScraper):
    source_name = "Zarplata.ru"
    source_url = "https://zarplata.ru"

    search_url = "https://zarplata.ru/search/vacancy"
    search_keyword = "Frontend"
    max_pages = 5
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
        items: list[dict[str, Any]] = []
        for page in range(self.max_pages):
            html = self._fetch_page(page)
            cards = self._parse_cards(html)
            if not cards:
                break
            items.extend(cards)
            if page < self.max_pages - 1:
                time.sleep(self.request_delay_seconds)
        return items

    def _fetch_page(self, page: int) -> str:
        params: dict[str, Any] = {
            "text": self.search_keyword,
            "search_field": "name",
            "area": 113,  # 113 = Россия целиком, тот же код areas, что у HH.ru
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

        match = self._external_id(href)
        if match is None:
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
            "external_id": match,
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
            "url": f"https://zarplata.ru{href}" if href.startswith("/") else href,
            "posted_at": None,  # список не отдаёт дату публикации отдельным полем
            "is_active": True,
        }

    @staticmethod
    def _external_id(href: str) -> str | None:
        # href вида "/vacancy/137651428?query=..."
        path = href.split("?", 1)[0]
        vacancy_id = path.rsplit("/", 1)[-1]
        return vacancy_id if vacancy_id.isdigit() else None

    @staticmethod
    def _parse_salary(card: Tag) -> tuple[int | None, int | None, str]:
        """
        Зарплата рендерится как последовательность <data value="180000">…</data>
        [– <data value="240000">…</data>] <data value="RUB">₽</data> — без
        отдельного data-qa. Опыт тоже рендерится через <data value="1-3">,
        поэтому отличаем по содержимому value: чистые цифры -> сумма,
        RUB/USD/EUR -> валюта, всё остальное (например "1-3") — не наше.
        """
        amounts: list[int] = []
        currency = Job.Currency.RUB
        for data_el in card.find_all("data"):
            value = data_el.get("value", "")
            if value in CURRENCY_MAP:
                currency = CURRENCY_MAP[value]
            elif value.isdigit():
                amounts.append(int(value))
        if len(amounts) >= 2:
            return amounts[0], amounts[1], currency
        if len(amounts) == 1:
            # Один <data> с суммой — понять "от" это или "до" по тексту рядом
            # ("–" после суммы значит "от X – Y", но Y не распарсился —
            # такое не встречалось на практике; практический случай —
            # единственная сумма без диапазона считаем нижней границей).
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
