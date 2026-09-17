import logging

from celery import shared_task

from apps.jobs.models import Job, JobNotification, UserJobFilter

from .client import send_message
from .formatting import format_job_message

logger = logging.getLogger(__name__)


@shared_task
def notify_users_for_jobs(job_ids: list[int]) -> dict:
    """
    Для каждой новой вакансии (job_ids — то, что вернул BaseScraper.run()
    в stats["new_job_ids"]) находит подписанных пользователей, чей фильтр
    подходит, и отправляет им сообщение в Telegram.
    """
    if not job_ids:
        return {"notified": 0}

    jobs = Job.objects.filter(id__in=job_ids).select_related("source")
    filters = list(
        UserJobFilter.objects.filter(
            is_active=True,
            user__telegram_notifications_enabled=True,
            user__telegram_chat_id__isnull=False,
        ).select_related("user")
    )

    notified = 0
    for job in jobs:
        notified_user_ids: set[int] = set()
        for job_filter in filters:
            if job_filter.user_id in notified_user_ids:
                continue
            if not job_filter.matches(job):
                continue
            notified_user_ids.add(job_filter.user_id)
            if _notify_one(job_filter.user, job):
                notified += 1

    logger.info("notify_users_for_jobs: %s job(s), %s notification(s) sent", len(job_ids), notified)
    return {"notified": notified}


def _notify_one(user, job: Job) -> bool:
    notification, created = JobNotification.objects.get_or_create(user=user, job=job)
    if not created:
        return False  # этому пользователю про эту вакансию уже писали

    ok = send_message(user.telegram_chat_id, format_job_message(job))
    if notification.sent_to_telegram != ok:
        notification.sent_to_telegram = ok
        notification.save(update_fields=["sent_to_telegram"])
    return ok
