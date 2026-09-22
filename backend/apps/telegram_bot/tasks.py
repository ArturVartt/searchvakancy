import logging

from celery import shared_task

from apps.jobs.models import Job, JobNotification, UserJobFilter

from .client import send_message
from .formatting import format_jobs_batch_message

logger = logging.getLogger(__name__)


@shared_task
def notify_users_for_jobs(job_ids: list[int]) -> dict:
    """
    Для новых вакансий (job_ids — то, что вернул BaseScraper.run() в
    stats["new_job_ids"], возможно со всех источников за один тик — см.
    apps/jobs/tasks.py:run_all_scrapers) находит подписанных пользователей,
    чей фильтр подходит, и отправляет им сообщение в Telegram.

    Важно: одному пользователю за один вызов уходит ОДНО сообщение со
    списком всех подходящих вакансий, а не по сообщению на каждую —
    иначе 10 вакансий, набежавших за 30 минут, превратились бы в 10
    сообщений подряд (см. format_jobs_batch_message). JobNotification в
    БД при этом создаётся по одной записи на вакансию — это отдельная
    история (нужна для /api/jobs/notifications/ и "отметить прочитанным"),
    группировка касается только отправки.
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

    pending_by_user: dict[int, list[Job]] = {}
    users_by_id = {}
    for job in jobs:
        matched_user_ids: set[int] = set()
        for job_filter in filters:
            if job_filter.user_id in matched_user_ids:
                continue
            if not job_filter.matches(job):
                continue
            matched_user_ids.add(job_filter.user_id)

            # get_or_create — идемпотентность на уровне (пользователь,
            # вакансия): если этому пользователю про эту вакансию уже
            # писали (например, при повторном вызове таска), не дублируем.
            _notification, created = JobNotification.objects.get_or_create(
                user=job_filter.user, job=job
            )
            if not created:
                continue
            users_by_id[job_filter.user_id] = job_filter.user
            pending_by_user.setdefault(job_filter.user_id, []).append(job)

    notified = 0
    for user_id, user_jobs in pending_by_user.items():
        user = users_by_id[user_id]
        ok = send_message(user.telegram_chat_id, format_jobs_batch_message(user_jobs))
        JobNotification.objects.filter(user=user, job__in=user_jobs).update(sent_to_telegram=ok)
        if ok:
            notified += len(user_jobs)

    logger.info(
        "notify_users_for_jobs: %s job(s), %s user(s), %s notification(s) sent",
        len(job_ids),
        len(pending_by_user),
        notified,
    )
    return {"notified": notified}
