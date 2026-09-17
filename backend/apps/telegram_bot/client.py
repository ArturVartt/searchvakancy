"""
Тонкий синхронный клиент Telegram Bot API поверх requests.

Используется из Celery-таска уведомлений (apps/telegram_bot/tasks.py) —
это НЕ то же самое, что long-polling бот (apps/telegram_bot/bot.py):
отправка сообщений не должна зависеть от того, запущен ли процесс бота.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"


def send_message(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN не задан — сообщение в Telegram не отправлено")
        return False

    url = TELEGRAM_API_URL.format(token=settings.TELEGRAM_BOT_TOKEN, method="sendMessage")
    try:
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        logger.exception("Не удалось отправить сообщение в Telegram chat_id=%s", chat_id)
        return False
