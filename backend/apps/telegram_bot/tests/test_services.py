import pytest

from apps.accounts.models import Customer
from apps.jobs.models import Job, JobSource, UserJobFilter
from apps.telegram_bot import services


@pytest.mark.django_db
def test_get_or_create_customer_creates_then_reuses_and_updates_username():
    c1 = services.get_or_create_customer(555, "artur")
    assert c1.username == "tg_555"
    assert c1.telegram_chat_id == "555"
    assert c1.telegram_username == "artur"

    c2 = services.get_or_create_customer(555, "artur_new")
    assert c2.pk == c1.pk
    assert c2.telegram_username == "artur_new"
    assert Customer.objects.filter(telegram_chat_id="555").count() == 1


@pytest.mark.django_db
def test_set_subscription_creates_default_filter_on_enable():
    services.get_or_create_customer(1, "u")
    assert UserJobFilter.objects.count() == 0

    services.set_subscription(1, True)
    customer = Customer.objects.get(telegram_chat_id="1")
    assert customer.telegram_notifications_enabled is True
    assert UserJobFilter.objects.filter(user=customer).count() == 1

    services.set_subscription(1, False)
    customer.refresh_from_db()
    assert customer.telegram_notifications_enabled is False
    # unsubscribe не удаляет фильтр, просто выключает флаг
    assert UserJobFilter.objects.filter(user=customer).count() == 1


@pytest.mark.django_db
def test_parse_filter_args():
    updates, unknown = services.parse_filter_args(
        ["min_salary=150000", "keywords=react,vue", "garbage", "max_salary=oops"]
    )
    assert updates == {"min_salary": 150000, "keywords": ["react", "vue"]}
    assert set(unknown) == {"garbage", "max_salary=oops"}


@pytest.mark.django_db
def test_apply_filter_updates_and_describe_filter():
    services.get_or_create_customer(2, "u2")
    services.apply_filter_updates(2, {"min_salary": 200000, "keywords": ["react"]})

    job_filter = UserJobFilter.objects.get(user__telegram_chat_id="2")
    assert job_filter.min_salary == 200000
    assert job_filter.keywords == ["react"]

    text = services.describe_filter(2)
    assert "200000" in text
    assert "react" in text


@pytest.mark.django_db
def test_reset_filter_clears_previous_constraints():
    services.get_or_create_customer(3, "u3")
    services.apply_filter_updates(3, {"min_salary": 500000})
    assert UserJobFilter.objects.get(user__telegram_chat_id="3").min_salary == 500000

    services.reset_filter(3)
    job_filter = UserJobFilter.objects.get(user__telegram_chat_id="3")
    assert job_filter.min_salary is None
    assert UserJobFilter.objects.filter(user__telegram_chat_id="3").count() == 1


@pytest.mark.django_db
def test_get_latest_jobs_orders_by_posted_at_desc_and_skips_inactive():
    source = JobSource.objects.create(name="HH.ru", url="https://hh.ru")
    old = Job.objects.create(
        source=source, external_id="1", title="Old", company="A",
        url="https://hh.ru/1", posted_at="2026-01-01T00:00:00Z",
    )
    new = Job.objects.create(
        source=source, external_id="2", title="New", company="B",
        url="https://hh.ru/2", posted_at="2026-02-01T00:00:00Z",
    )
    Job.objects.create(
        source=source, external_id="3", title="Inactive", company="C",
        url="https://hh.ru/3", posted_at="2026-03-01T00:00:00Z", is_active=False,
    )

    jobs = services.get_latest_jobs(limit=5)
    assert [j.id for j in jobs] == [new.id, old.id]
