"""
Реестр скрейперов: ключ -> класс. Добавление нового источника — это
всегда только новая запись здесь, ядро (tasks.py, admin) не трогаем.
"""
from .habr_scraper import HabrScraper
from .hh_scraper import HHScraper

SCRAPERS = {
    "hh": HHScraper,
    "habr": HabrScraper,
    # "vk": VKScraper,  # см. README — vk.com/jobs оказался не тем, чем выглядит
}
