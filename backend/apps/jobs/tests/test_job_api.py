import pytest

from apps.jobs.models import Job


def _make_job(source, **kwargs):
    defaults = dict(
        source=source,
        external_id=kwargs.pop("external_id", "1"),
        title="Frontend Developer",
        company="Acme",
        url="https://hh.ru/1",
        location="Москва",
        experience_level=Job.ExperienceLevel.MIDDLE,
        job_type=Job.JobType.FULL_TIME,
    )
    defaults.update(kwargs)
    return Job.objects.create(**defaults)


@pytest.mark.django_db
def test_job_list_is_public(api_client, source):
    _make_job(source)
    response = api_client.get("/api/jobs/")
    assert response.status_code == 200
    assert response.data["count"] == 1


@pytest.mark.django_db
def test_job_list_excludes_inactive(api_client, source):
    _make_job(source, external_id="1")
    _make_job(source, external_id="2", is_active=False)
    response = api_client.get("/api/jobs/")
    assert response.data["count"] == 1


@pytest.mark.django_db
def test_filter_by_min_salary_uses_effective_salary_like_matches(api_client, source):
    # job1: salary_to=180000 -> эффективная зарплата для min_salary = 180000
    job1 = _make_job(source, external_id="1", salary_from=None, salary_to=180000)
    # job2: только salary_from=100000, salary_to не указан -> эффективная = 100000
    job2 = _make_job(source, external_id="2", salary_from=100000, salary_to=None)

    response = api_client.get("/api/jobs/", {"min_salary": 150000})
    ids = {row["id"] for row in response.data["results"]}
    assert ids == {job1.id}
    assert job2.id not in ids


@pytest.mark.django_db
def test_filter_by_experience_level(api_client, source):
    junior = _make_job(source, external_id="1", experience_level=Job.ExperienceLevel.JUNIOR)
    _make_job(source, external_id="2", experience_level=Job.ExperienceLevel.SENIOR)

    response = api_client.get("/api/jobs/", {"experience_level": "junior"})
    ids = {row["id"] for row in response.data["results"]}
    assert ids == {junior.id}


@pytest.mark.django_db
def test_filter_by_location_icontains(api_client, source):
    spb = _make_job(source, external_id="1", location="Санкт-Петербург")
    _make_job(source, external_id="2", location="Новосибирск")

    response = api_client.get("/api/jobs/", {"location": "петерб"})
    ids = {row["id"] for row in response.data["results"]}
    assert ids == {spb.id}


@pytest.mark.django_db
def test_search_by_title(api_client, source):
    react_job = _make_job(source, external_id="1", title="React Developer")
    _make_job(source, external_id="2", title="Backend Developer (Go)")

    response = api_client.get("/api/jobs/", {"search": "React"})
    ids = {row["id"] for row in response.data["results"]}
    assert ids == {react_job.id}


@pytest.mark.django_db
def test_detail_returns_full_fields(api_client, source):
    job = _make_job(source, description="Опыт с React от 2 лет")
    response = api_client.get(f"/api/jobs/{job.id}/")
    assert response.status_code == 200
    assert response.data["description"] == "Опыт с React от 2 лет"
    assert response.data["source"]["name"] == "HH.ru"


@pytest.mark.django_db
def test_stats_endpoint(api_client, source):
    _make_job(source, external_id="1", experience_level=Job.ExperienceLevel.JUNIOR)
    _make_job(source, external_id="2", experience_level=Job.ExperienceLevel.SENIOR)
    _make_job(source, external_id="3", is_active=False)

    response = api_client.get("/api/jobs/stats/")
    assert response.status_code == 200
    assert response.data["total_active"] == 2
    by_source = {row["source"]: row["count"] for row in response.data["by_source"]}
    assert by_source == {"HH.ru": 2}
