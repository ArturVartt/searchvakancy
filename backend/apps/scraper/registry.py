"""
Реестр скрейперов: ключ -> класс. Добавление нового источника — это
всегда только новая запись здесь, ядро (tasks.py, admin) не трогаем.
"""
from .habr_scraper import HabrScraper
from .hh_scraper import HHScraper
from .hhuz_scraper import HHUzScraper
from .itjobsuz_scraper import ItJobsUzScraper
from .staffam_scraper import StaffAmScraper
from .superjob_scraper import SuperJobScraper
from .tg_remote_frontend_scraper import TgRemoteFrontendScraper
from .vk_scraper import VKScraper
from .zarplata_scraper import ZarplataScraper

SCRAPERS = {
    "hh": HHScraper,
    "habr": HabrScraper,
    "superjob": SuperJobScraper,
    "zarplata": ZarplataScraper,
    "itjobsuz": ItJobsUzScraper,
    "vk": VKScraper,
    "staffam": StaffAmScraper,
    "hhuz": HHUzScraper,
    "tgremotefrontend": TgRemoteFrontendScraper,
}
