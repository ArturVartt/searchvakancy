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
    "react",
    "vue",
    "angular",
    "javascript",
    "typescript",
    "html",
    "css",
)


def strip_html(html: str | None) -> str:
    """Убрать теги (в т.ч. <highlighttext> у HH) и лишние пробелы."""
    if not html:
        return ""
    text = BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def is_frontend_relevant(title: str, description: str = "") -> bool:
    haystack = f"{title} {description}".lower()
    return any(keyword in haystack for keyword in FRONTEND_KEYWORDS)
