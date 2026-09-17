"""
Long-polling Telegram-бот (python-telegram-bot v21, async).

Вся бизнес-логика (Django ORM) — в services.py, обычные синхронные
функции; здесь только адаптация к telegram.ext: парсинг Update/Context,
sync_to_async, форматирование ответа.

Запуск: `python manage.py runbot` (apps/telegram_bot/management/commands/runbot.py).

Отправка уведомлений о НОВЫХ вакансиях идёт отдельно, из Celery
(apps/telegram_bot/tasks.py, через client.send_message) — не зависит
от того, запущен ли этот процесс.
"""
import logging

from asgiref.sync import sync_to_async
from django.conf import settings
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from apps.jobs.models import Job

from . import services
from .formatting import format_job_message

logger = logging.getLogger(__name__)

LATEST_JOBS_LIMIT = 5


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    await sync_to_async(services.get_or_create_customer)(chat.id, chat.username or "")
    await update.message.reply_text(
        "Привет! Я бот SearchVakancy — присылаю новые вакансии Frontend-разработчика "
        "из HH.ru, VK Jobs и Habr Career.\n\n"
        "/subscribe — включить уведомления\n"
        "/unsubscribe — выключить уведомления\n"
        "/latest — последние вакансии\n"
        "/filters — посмотреть или настроить фильтр\n"
        "/trending — что сейчас популярно в требованиях"
    )


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    await sync_to_async(services.get_or_create_customer)(chat.id, chat.username or "")
    await sync_to_async(services.set_subscription)(chat.id, True)
    await update.message.reply_text(
        "Подписка включена ✅ Буду присылать новые вакансии по вашему фильтру "
        "(сейчас — без ограничений, все вакансии). Настроить: /filters"
    )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    await sync_to_async(services.get_or_create_customer)(chat.id, chat.username or "")
    await sync_to_async(services.set_subscription)(chat.id, False)
    await update.message.reply_text("Подписка выключена. Вернуть — /subscribe")


async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    await sync_to_async(services.get_or_create_customer)(chat.id, chat.username or "")
    jobs = await sync_to_async(services.get_latest_jobs)(LATEST_JOBS_LIMIT)
    if not jobs:
        await update.message.reply_text("Пока нет вакансий в базе — загляните позже.")
        return
    text = "\n\n———\n\n".join(format_job_message(job) for job in jobs)
    await update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)


async def filters_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    await sync_to_async(services.get_or_create_customer)(chat.id, chat.username or "")

    if not context.args:
        text = await sync_to_async(services.describe_filter)(chat.id)
        await update.message.reply_text(text)
        return

    if context.args == ["reset"]:
        await sync_to_async(services.reset_filter)(chat.id)
        await update.message.reply_text("Фильтр сброшен — теперь без ограничений.")
        return

    updates, unknown = services.parse_filter_args(context.args)
    if updates:
        await sync_to_async(services.apply_filter_updates)(chat.id, updates)

    reply_lines = []
    if updates:
        reply_lines.append(f"Обновлено: {', '.join(updates)}.")
    if unknown:
        reply_lines.append(
            "Не распознано: "
            + ", ".join(unknown)
            + "\n\nПример: /filters min_salary=150000 keywords=react,vue locations=Москва,Удалённо experience=junior,middle"
        )
    if not reply_lines:
        reply_lines.append("Ничего не изменено.")
    await update.message.reply_text("\n".join(reply_lines))


async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    await sync_to_async(services.get_or_create_customer)(chat.id, chat.username or "")

    total, top_skills, top_experience = await sync_to_async(services.get_trending_stats)()
    if total == 0:
        await update.message.reply_text("Пока нет активных вакансий для статистики.")
        return

    exp_labels = dict(Job.ExperienceLevel.choices)
    lines = [f"📊 Активных вакансий: {total}", "", "Топ технологий/навыков:"]
    lines += [f"  • {skill} — {count}" for skill, count in top_skills] or ["  нет данных"]
    lines += ["", "По уровню опыта:"]
    lines += [f"  • {exp_labels.get(level, level)} — {count}" for level, count in top_experience] or [
        "  нет данных"
    ]
    await update.message.reply_text("\n".join(lines))


def build_application() -> Application:
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("latest", latest))
    application.add_handler(CommandHandler("filters", filters_cmd))
    application.add_handler(CommandHandler("trending", trending))
    return application
