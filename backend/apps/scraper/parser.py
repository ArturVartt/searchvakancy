"""Утилиты нормализации, общие для всех скрейперов."""
import re

from bs4 import BeautifulSoup

# Ключевые слова, по которым отсеиваем вакансии не про frontend —
# полезно для источников без нормального серверного фильтра поиска.
FRONTEND_KEYWORDS = (
    "frontend",
    "front-end",
    "front end",
    "фронтенд",
    "фронт-энд",
    "frontend engineer",
    "frontend developer",
    "frontend разработчик",
    "product engineer",
    "react",
    "react.js",
    "vue",
    "javascript",
    "typescript",
    "html",
    "css",
    "next.js",
)

# Если встречается любое из этих слов — вакансия отсеивается, даже если
# рядом упоминается React/Vue/etc: владелец проекта не хочет видеть
# full-stack позиции в ленте "Frontend". Проверяем три написания
# ("fullstack"/"full-stack"/"full stack"), потому что "fullstack" не
# матчится как подстрока в "full-stack"/"full stack" из-за разделителя.
FRONTEND_EXCLUDE_KEYWORDS = (
    "fullstack",
    "full-stack",
    "full stack",
)


def strip_html(html: str | None) -> str:
    """Убрать теги (в т.ч. <highlighttext> у HH) и лишние пробелы."""
    if not html:
        return ""
    text = BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def is_frontend_relevant(title: str, description: str = "") -> bool:
    haystack = f"{title} {description}".lower()
    if any(keyword in haystack for keyword in FRONTEND_EXCLUDE_KEYWORDS):
        return False
    return any(keyword in haystack for keyword in FRONTEND_KEYWORDS)
