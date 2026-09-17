import pytest

from apps.jobs.models import FavoriteJob, Job, JobNotification, UserJobFilter


def _make_job(source, external_id="1", **kwargs):
    defaults = dict(
        source=source, external_id=external_id, title="Frontend Developer",
        company="Acme", url=f"https://hh.ru/{external_id}",
    )
    defaults.update(kwargs)
    return Job.objects.create(**defaults)


# --- /api/jobs/filters/ ------------------------------------------------


@pytest.mark.django_db
def test_filters_require_auth(api_client):
    response = api_client.get("/api/jobs/filters/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_filters_crud_scoped_to_user(auth_client, user, other_user):
    UserJobFilter.objects.create(user=other_user, min_salary=999999)

    create = auth_client.post("/api/jobs/filters/", {"min_salary": 150000, "keywords": ["react"]}, format="json")
    assert create.status_code == 201
    filter_id = create.data["id"]

    listed = auth_client.get("/api/jobs/filters/")
    assert listed.data["count"] == 1  # чужой фильтр не виден
    assert listed.data["results"][0]["id"] == filter_id

    patched = auth_client.patch(f"/api/jobs/filters/{filter_id}/", {"min_salary": 200000}, format="json")
    assert patched.status_code == 200
    assert patched.data["min_salary"] == 200000

    deleted = auth_client.delete(f"/api/jobs/filters/{filter_id}/")
    assert deleted.status_code == 204
    assert UserJobFilter.objects.filter(user=user).count() == 0


@pytest.mark.django_db
def test_cannot_access_other_users_filter(auth_client, other_user):
    other_filter = UserJobFilter.objects.create(user=other_user)
    response = auth_client.get(f"/api/jobs/filters/{other_filter.id}/")
    assert response.status_code == 404


# --- /api/jobs/<id>/favorite/ и /api/jobs/favorites/ --------------------


@pytest.mark.django_db
def test_favorite_requires_auth(api_client, source):
    job = _make_job(source)
    response = api_client.post(f"/api/jobs/{job.id}/favorite/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_favorite_add_list_remove(auth_client, source):
    job = _make_job(source)

    added = auth_client.post(f"/api/jobs/{job.id}/favorite/")
    assert added.status_code == 201
    assert FavoriteJob.objects.filter(job=job).count() == 1

    # повторное добавление — идемпотентно, не дублирует
    again = auth_client.post(f"/api/jobs/{job.id}/favorite/")
    assert again.status_code == 200
    assert FavoriteJob.objects.filter(job=job).count() == 1

    listed = auth_client.get("/api/jobs/favorites/")
    assert listed.data["count"] == 1
    assert listed.data["results"][0]["id"] == job.id

    detail = auth_client.get(f"/api/jobs/{job.id}/")
    assert detail.data["is_favorited"] is True

    removed = auth_client.delete(f"/api/jobs/{job.id}/favorite/")
    assert removed.status_code == 204
    assert FavoriteJob.objects.filter(job=job).count() == 0


@pytest.mark.django_db
def test_is_favorited_false_for_anonymous(api_client, source):
    job = _make_job(source)
    response = api_client.get(f"/api/jobs/{job.id}/")
    assert response.data["is_favorited"] is False


# --- /api/jobs/notifications/ -------------------------------------------


@pytest.mark.django_db
def test_notifications_scoped_to_user_and_mark_read(auth_client, user, other_user, source):
    job = _make_job(source)
    mine = JobNotification.objects.create(user=user, job=job)
    JobNotification.objects.create(user=other_user, job=job)

    listed = auth_client.get("/api/jobs/notifications/")
    assert listed.data["count"] == 1
    assert listed.data["results"][0]["id"] == mine.id
    assert listed.data["results"][0]["is_read"] is False

    marked = auth_client.post(f"/api/jobs/notifications/{mine.id}/mark_read/")
    assert marked.status_code == 200
    mine.refresh_from_db()
    assert mine.is_read is True


# --- токен-аутентификация -------------------------------------------------


@pytest.mark.django_db
def test_obtain_token_and_use_it(api_client, user):
    response = api_client.post("/api/auth/token/", {"username": "alice", "password": "pass12345"})
    assert response.status_code == 200
    token = response.data["token"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
    me = api_client.get("/api/jobs/filters/")
    assert me.status_code == 200  # токен принят, доступ к защищённому эндпоинту есть
