"""
Синхронная бизнес-логика Telegram-бота (работа с Django ORM).

Вынесена отдельно от bot.py, чтобы:
  1) не мешать asyncio с sync_to_async там, где это не нужно для тестов —
     эти функции тестируются напрямую, без event loop;
  2) bot.py оставался тонким слоем адаптации к telegram.ext (парсинг
     Update/Context, вызов sync_to_async, форматирование ответа).
"""
from collections import Counter

from apps.accounts.models import Customer
from apps.jobs.models import Job, UserJobFilter
from apps.scraper.parser import FRONTEND_KEYWORDS

TRENDING_TOP_N = 10

FILTER_LIST_FIELDS = {
    "keywords": "keywords",
    "excluded_keywords": "excluded_keywords",
    "locations": "locations",
    "experience": "experience_levels",
    "job_types": "job_types",
}
FILTER_INT_FIELDS = {"min_salary": "min_salary", "max_salary": "max_salary"}


def get_or_create_customer(chat_id: int, username: str = "") -> Customer:
    customer, _ = Customer.objects.get_or_create(
        telegram_chat_id=str(chat_id),
        defaults={"username": f"tg_{chat_id}", "telegram_username": username or ""},
    )
    if username and customer.telegram_username != username:
        customer.telegram_username = username
        customer.save(update_fields=["telegram_username"])
    return customer


def set_subscription(chat_id: int, enabled: bool) -> None:
    customer = Customer.objects.get(telegram_chat_id=str(chat_id))
    customer.telegram_notifications_enabled = enabled
    customer.save(update_fields=["telegram_notifications_enabled"])
    if enabled:
        # Фильтр без ограничений = получать вообще все новые вакансии,
        # пока пользователь не сузит его через /filters.
        UserJobFilter.objects.get_or_create(user=customer)


def get_latest_jobs(limit: int) -> list[Job]:
    return list(
        Job.objects.filter(is_active=True)
        .select_related("source")
        .order_by("-posted_at", "-created_at")[:limit]
    )


def describe_filter(chat_id: int) -> str:
    customer = Customer.objects.get(telegram_chat_id=str(chat_id))
    job_filter = UserJobFilter.objects.filter(user=customer).order_by("-updated_at").first()
    status = "включены" if customer.telegram_notifications_enabled else "выключены"
    if job_filter is None:
        return f"Уведомления: {status}.\nФильтр не настроен — /subscribe создаст фильтр без ограничений."

    return "\n".join(
        [
            f"Уведомления: {status}.",
            "Текущий фильтр:",
            f"  зарплата: {job_filter.min_salary or '—'}–{job_filter.max_salary or '—'}",
            f"  города: {', '.join(job_filter.locations) or 'любые'}",
            f"  опыт: {', '.join(job_filter.experience_levels) or 'любой'}",
            f"  тип занятости: {', '.join(job_filter.job_types) or 'любой'}",
            f"  ключевые слова: {', '.join(job_filter.keywords) or '—'}",
            f"  исключить: {', '.join(job_filter.excluded_keywords) or '—'}",
        ]
    )


def apply_filter_updates(chat_id: int, updates: dict) -> UserJobFilter:
    customer = Customer.objects.get(telegram_chat_id=str(chat_id))
    job_filter, _ = UserJobFilter.objects.get_or_create(user=customer)
    for field, value in updates.items():
        setattr(job_filter, field, value)
    job_filter.save()
    return job_filter


def reset_filter(chat_id: int) -> UserJobFilter:
    customer = Customer.objects.get(telegram_chat_id=str(chat_id))
    UserJobFilter.objects.filter(user=customer).delete()
    return UserJobFilter.objects.create(user=customer)


def get_trending_stats() -> tuple[int, list[tuple[str, int]], list[tuple[str, int]]]:
    rows = Job.objects.filter(is_active=True).values_list(
        "title", "description", "required_skills", "experience_level"
    )
    skill_counter: Counter[str] = Counter()
    exp_counter: Counter[str] = Counter()
    total = 0
    for title, description, skills, experience_level in rows:
        total += 1
        if skills:
            skill_counter.update(s.strip().lower() for s in skills if s.strip())
        else:
            haystack = f"{title} {description}".lower()
            skill_counter.update(kw for kw in FRONTEND_KEYWORDS if kw in haystack)
        if experience_level:
            exp_counter[experience_level] += 1
    return total, skill_counter.most_common(TRENDING_TOP_N), exp_counter.most_common()


def split_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def parse_filter_args(args: list[str]) -> tuple[dict, list[str]]:
    """token вида key=value -> {model_field: value}; вернёт также нераспознанные токены."""
    updates: dict = {}
    unknown: list[str] = []
    for token in args:
        if "=" not in token:
            unknown.append(token)
            continue
        key, _, raw_value = token.partition("=")
        key = key.strip().lower()
        if key in FILTER_LIST_FIELDS:
            updates[FILTER_LIST_FIELDS[key]] = split_list(raw_value)
        elif key in FILTER_INT_FIELDS:
            try:
                updates[FILTER_INT_FIELDS[key]] = int(raw_value.strip())
            except ValueError:
                unknown.append(token)
        else:
            unknown.append(token)
    return updates, unknown
