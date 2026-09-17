from django.conf import settings
from django.core.management.base import BaseCommand
from telegram import Update

from apps.telegram_bot.bot import build_application


class Command(BaseCommand):
    help = "Запустить Telegram-бота SearchVakancy (long polling)"

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            self.stderr.write(
                self.style.ERROR(
                    "TELEGRAM_BOT_TOKEN не задан. Получите токен у @BotFather "
                    "и добавьте его в .env, затем перезапустите."
                )
            )
            return

        application = build_application()
        self.stdout.write(self.style.SUCCESS("Бот запущен (long polling)…"))
        application.run_polling(allowed_updates=Update.ALL_TYPES)
