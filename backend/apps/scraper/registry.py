"""
Реестр скрейперов: ключ -> класс. Добавление нового источника — это
всегда только новая запись здесь, ядро (tasks.py, admin) не трогаем.
"""
from .habr_scraper import HabrScraper
from .hh_scraper import HHScraper
from .itjobsuz_scraper import ItJobsUzScraper
from .superjob_scraper import SuperJobScraper
from .zarplata_scraper import ZarplataScraper

SCRAPERS = {
    "hh": HHScraper,
    "habr": HabrScraper,
    "superjob": SuperJobScraper,
    "zarplata": ZarplataScraper,
    "itjobsuz": ItJobsUzScraper,
    # "vk": VKScraper,  # см. README — vk.com/jobs оказался не тем, чем выглядит
}
