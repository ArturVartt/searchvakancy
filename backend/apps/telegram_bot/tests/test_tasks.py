from unittest.mock import patch

import pytest

from apps.accounts.models import Customer
from apps.jobs.models import Job, JobNotification, JobSource, UserJobFilter
from apps.telegram_bot.tasks import notify_users_for_jobs


def _make_job(source, external_id="1", title="Frontend Dev", salary_from=None, location="Москва"):
    return Job.objects.create(
        source=source,
        external_id=external_id,
        title=title,
        company="Acme",
        url=f"https://hh.ru/{external_id}",
        salary_from=salary_from,
        location=location,
    )


@pytest.mark.django_db
def test_notify_users_for_jobs_sends_to_matching_subscribed_user():
    source = JobSource.objects.create(name="HH.ru", url="https://hh.ru")
    job = _make_job(source, salary_from=200000)

    user = Customer.objects.create(
        username="tg_1", telegram_chat_id="1", telegram_notifications_enabled=True
    )
    UserJobFilter.objects.create(user=user, min_salary=150000)

    with patch("apps.telegram_bot.tasks.send_message", return_value=True) as mocked_send:
        result = notify_users_for_jobs([job.id])

    assert result == {"notified": 1}
    mocked_send.assert_called_once()
    assert mocked_send.call_args.args[0] == "1"
    assert job.title in mocked_send.call_args.args[1]

    notification = JobNotification.objects.get(user=user, job=job)
    assert notification.sent_to_telegram is True


@pytest.mark.django_db
def test_notify_users_for_jobs_skips_non_matching_filter():
    source = JobSource.objects.create(name="HH.ru", url="https://hh.ru")
    job = _make_job(source, salary_from=100000)  # ниже min_salary фильтра

    user = Customer.objects.create(
        username="tg_2", telegram_chat_id="2", telegram_notifications_enabled=True
    )
    UserJobFilter.objects.create(user=user, min_salary=300000)

    with patch("apps.telegram_bot.tasks.send_message", return_value=True) as mocked_send:
        result = notify_users_for_jobs([job.id])

    assert result == {"notified": 0}
    mocked_send.assert_not_called()
    assert not JobNotification.objects.filter(user=user, job=job).exists()


@pytest.mark.django_db
def test_notify_users_for_jobs_ignores_disabled_and_unsubscribed_users():
    source = JobSource.objects.create(name="HH.ru", url="https://hh.ru")
    job = _make_job(source)

    disabled = Customer.objects.create(
        username="tg_3", telegram_chat_id="3", telegram_notifications_enabled=False
    )
    UserJobFilter.objects.create(user=disabled)

    with patch("apps.telegram_bot.tasks.send_message", return_value=True) as mocked_send:
        result = notify_users_for_jobs([job.id])

    assert result == {"notified": 0}
    mocked_send.assert_not_called()


@pytest.mark.django_db
def test_notify_users_for_jobs_is_idempotent_per_user_job_pair():
    source = JobSource.objects.create(name="HH.ru", url="https://hh.ru")
    job = _make_job(source)

    user = Customer.objects.create(
        username="tg_4", telegram_chat_id="4", telegram_notifications_enabled=True
    )
    UserJobFilter.objects.create(user=user)

    with patch("apps.telegram_bot.tasks.send_message", return_value=True) as mocked_send:
        notify_users_for_jobs([job.id])
        result = notify_users_for_jobs([job.id])  # повторный запуск для той же вакансии

    assert result == {"notified": 0}  # уже уведомляли — повторно не шлём
    assert mocked_send.call_count == 1
    assert JobNotification.objects.filter(user=user, job=job).count() == 1
