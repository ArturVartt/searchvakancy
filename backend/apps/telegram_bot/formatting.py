"""Форматирование сообщений о вакансиях для Telegram (HTML parse_mode)."""
from html import escape

from apps.jobs.models import Job

EXPERIENCE_LABELS = dict(Job.ExperienceLevel.choices)


def _format_salary(job: Job) -> str:
    if not job.salary_from and not job.salary_to:
        return "з/п не указана"
    if job.salary_from and job.salary_to:
        return f"{job.salary_from:,}–{job.salary_to:,} {job.currency}".replace(",", " ")
    amount = job.salary_from or job.salary_to
    prefix = "от" if job.salary_from else "до"
    return f"{prefix} {amount:,} {job.currency}".replace(",", " ")


def format_job_message(job: Job) -> str:
    lines = [
        f"💼 <b>{escape(job.title)}</b>",
        escape(job.company),
        "",
        f"💰 {_format_salary(job)}",
    ]
    if job.location:
        lines.append(f"📍 {escape(job.location)}")
    if job.experience_level:
        lines.append(f"📊 {EXPERIENCE_LABELS.get(job.experience_level, job.experience_level)}")
    lines.append("")
    lines.append(f'<a href="{escape(job.url)}">Открыть вакансию</a> · {escape(job.source.name)}')
    return "\n".join(lines)


# Telegram режет сообщения по 4096 символам. При обычной работе (тик раз
# в 30 мин) вакансий за один раз мало, но на всякий случай ограничиваем
# число вакансий в одном сообщении — остальное показываем сводкой.
MAX_JOBS_PER_MESSAGE = 15


def _format_job_line(job: Job) -> str:
    parts = [f'<b>{escape(job.title)}</b> — {escape(job.company)}', f"💰 {_format_salary(job)}"]
    if job.location:
        parts.append(f"📍 {escape(job.location)}")
    return " · ".join(parts) + f'\n<a href="{escape(job.url)}">Открыть</a> · {escape(job.source.name)}'


def format_jobs_batch_message(jobs: list[Job]) -> str:
    """
    Одно сообщение на пачку новых вакансий за прогон скрейпера — вместо
    сообщения на каждую вакансию (иначе 10 вакансий за 30 минут = 10
    сообщений подряд). При одной вакансии — привычный подробный формат
    (format_job_message), при нескольких — компактный нумерованный список.
    """
    if len(jobs) == 1:
        return format_job_message(jobs[0])

    shown = jobs[:MAX_JOBS_PER_MESSAGE]
    lines = [f"🆕 <b>{len(jobs)} новых вакансий</b> по вашему фильтру:", ""]
    for i, job in enumerate(shown, start=1):
        lines.append(f"{i}. {_format_job_line(job)}")
        lines.append("")
    remaining = len(jobs) - len(shown)
    if remaining > 0:
        lines.append(f"…и ещё {remaining} — смотрите на сайте.")
    return "\n".join(lines).rstrip()
