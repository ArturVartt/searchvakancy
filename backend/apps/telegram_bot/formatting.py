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
