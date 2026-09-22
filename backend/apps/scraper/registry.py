"""
Реестр скрейперов: ключ -> класс. Добавление нового источника — это
всегда только новая запись здесь, ядро (tasks.py, admin) не трогаем.
"""
from .habr_scraper import HabrScraper
from .hh_scraper import HHScraper
from .superjob_scraper import SuperJobScraper

SCRAPERS = {
    "hh": HHScraper,
    "habr": HabrScraper,
    "superjob": SuperJobScraper,
    # "vk": VKScraper,  # см. README — vk.com/jobs оказался не тем, чем выглядит
}
