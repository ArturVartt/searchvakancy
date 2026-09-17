"""
Скрейпер Habr Career (career.habr.com) — публичного API у них нет,
парсим HTML списка вакансий (BeautifulSoup). Разметка снята вручную
с реальной страницы на 17.09.2026; если Habr перевёрстает список,
здесь всё, что может сломаться (см. класс vacancy-card__*).

Важно (проверено вручную на живом сайте): параметр ?specializations=
на самом деле НЕ фильтрует список — сервер возвращает общую ленту
вакансий (экономисты, рекрутёры и т.д. вперемешку с фронтендом).
Рабочий вариант — полнотекстовый поиск ?q=frontend, но и он не строгий
(ищет по всему тексту вакансии, не только по должности), поэтому
is_frontend_relevant() по заголовку — обязательная вторая проверка,
а не подстраховка "на всякий случай".
"""
import logging
import re
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

GRADE_MAP = {
    "Intern": Job.ExperienceLevel.JUNIOR,
    "Junior": Job.ExperienceLevel.JUNIOR,
    "Middle": Job.ExperienceLevel.MIDDLE,
    "Senior": Job.ExperienceLevel.SENIOR,
    "Lead": Job.ExperienceLevel.LEAD,
}

CURRENCY_SYMBOLS = {"₽": Job.Currency.RUB, "$": Job.Currency.USD, "€": Job.Currency.EUR}


class HabrScraper(BaseScraper):
    source_name = "Habr Career"
    source_url = "https://career.habr.com"

    base_url = "https://career.habr.com/vacancies"
    search_query = "frontend"
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
        for page in range(1, self.max_pages + 1):
            html = self._fetch_page(page)
            cards = self._parse_cards(html)
            if not cards and page > 1:
                break
            items.extend(cards)
            if page < self.max_pages:
                time.sleep(self.request_delay_seconds)
        return items

    def _fetch_page(self, page: int) -> str:
        params: dict[str, Any] = {"q": self.search_query, "type": "all"}
        if page > 1:
            params["page"] = page
        response = self.session.get(self.base_url, params=params, timeout=10)
        response.raise_for_status()
        return response.text

    def _parse_cards(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        parsed = (self._parse_one_card(card) for card in soup.select("div.vacancy-card"))
        return [item for item in parsed if item is not None]

    def _parse_one_card(self, card: Tag) -> dict[str, Any] | None:
        title_link = card.select_one("a.vacancy-card__title-link")
        if title_link is None:
            return None

        href = title_link.get("href", "")
        match = re.search(r"/vacancies/(\d+)", href)
        if not match:
            return None
        external_id = match.group(1)
        title = title_link.get_text(strip=True)

        skills = [s.get_text(strip=True) for s in card.select(".vacancy-card__skills-chip .basic-chip__text")]

        # Habr's ?specializations= фильтр негерметичен — отсекаем то, что
        # проскочило мимо (см. докстринг модуля).
        if not is_frontend_relevant(title, " ".join(skills)):
            return None

        company_link = card.select_one(".vacancy-card__company a.link-comp")
        company = company_link.get_text(strip=True) if company_link else ""

        date_tag = card.select_one("time.basic-date")
        posted_at_raw = date_tag.get("datetime") if date_tag else None
        posted_at: datetime | None = parse_datetime(posted_at_raw) if posted_at_raw else None

        salary_from, salary_to, currency = self._parse_salary(card)
        experience_level, employment_type, location = self._parse_meta_chips(card)
        if not location and employment_type == Job.EmploymentType.REMOTE:
            location = "Удалённо"

        return {
            "external_id": external_id,
            "title": title,
            "company": company,
            # Список вакансий не отдаёт полное описание (только теги
            # навыков) — доставать его значило бы N+1 запросов на детальную
            # страницу каждой вакансии. Тот же компромисс, что у HH-скрейпера.
            "description": "",
            "salary_from": salary_from,
            "salary_to": salary_to,
            "currency": currency,
            "location": location,
            "job_type": "",
            "experience_level": experience_level,
            "employment_type": employment_type,
            "required_skills": skills,
            "nice_to_have": [],
            "url": f"https://career.habr.com{href}" if href.startswith("/") else href,
            "posted_at": posted_at,
            "is_active": True,
        }

    @staticmethod
    def _parse_salary(card: Tag) -> tuple[int | None, int | None, str]:
        """
        Реальные форматы (проверено на живом сайте — НЕ "X - Y ₽" через
        тире, как можно было бы предположить):
          "от 200 000 ₽"        -> (200000, None)
          "до 188 000 ₽"        -> (None, 188000)
          "от 70 000 до 150 000 ₽" -> (70000, 150000)
          "от 2000 до 3000 $"   -> (2000, 3000, USD)

        "от" и "до" вытаскиваются НЕЗАВИСИМЫМИ регексами — если сначала
        проверить text.startswith("от") и на этом основании схватить все
        цифры строки целиком, диапазон "от X до Y" склеится в одно число
        (70000 + 150000 -> 70000150000), которое не лезет в IntegerField.
        """
        salary_tag = card.select_one(".basic-salary")
        if salary_tag is None:
            return None, None, Job.Currency.RUB
        text = salary_tag.get_text(strip=True)

        currency = Job.Currency.RUB
        for symbol, code in CURRENCY_SYMBOLS.items():
            if symbol in text:
                currency = code
                break

        def _extract(prefix: str) -> int | None:
            match = re.search(rf"{prefix}\s*([\d\s]+)", text)
            if not match:
                return None
            digits = re.sub(r"\D", "", match.group(1))
            return int(digits) if digits else None

        salary_from = _extract("от")
        salary_to = _extract("до")
        if salary_from is None and salary_to is None:
            # ни "от", ни "до" — вероятно точная сумма без предлога
            digits = re.sub(r"\D", "", text)
            if digits:
                salary_from = salary_to = int(digits)
        return salary_from, salary_to, currency

    @staticmethod
    def _parse_meta_chips(card: Tag) -> tuple[str, str, str]:
        experience_level = ""
        employment_type = ""
        location = ""
        for chip in card.select(".vacancy-card__meta .basic-chip"):
            svg = chip.find("svg")
            text_el = chip.select_one(".chip-with-icon__text")
            if svg is None or text_el is None:
                continue
            icon_name = next(
                (
                    cls.replace("svg-icon--icon-", "")
                    for cls in svg.get("class", [])
                    if cls.startswith("svg-icon--icon-")
                ),
                None,
            )
            text = text_el.get_text(strip=True)
            if icon_name == "grade":
                experience_level = GRADE_MAP.get(text, "")
            elif icon_name == "format":
                employment_type = (
                    Job.EmploymentType.REMOTE if "удал" in text.lower() else Job.EmploymentType.FULL_DAY
                )
            elif icon_name == "placemark":
                location = text
        return experience_level, employment_type, location

    def normalize_job(self, raw: dict[str, Any]) -> dict[str, Any]:
        # В отличие от HH (raw = сырой JSON API), здесь _parse_one_card уже
        # собрал финальный словарь под поля Job — normalize_job тождественна.
        return raw
