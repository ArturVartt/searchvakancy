import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.applications.models import Application
from apps.jobs.models import Job, JobSource
from apps.profiles.models import ProfileSet


def _pdf_file() -> SimpleUploadedFile:
    return SimpleUploadedFile("resume.pdf", b"%PDF-1.4 x", content_type="application/pdf")


@pytest.fixture
def job(db) -> Job:
    source = JobSource.objects.create(name="HH.ru", url="https://hh.ru")
    return Job.objects.create(
        source=source, external_id="1", title="Frontend Developer", company="Acme", url="https://hh.ru/1"
    )


@pytest.fixture
def profile_set(user) -> ProfileSet:
    return ProfileSet.objects.create(user=user, name="Frontend RU", resume=_pdf_file())


@pytest.mark.django_db
def test_create_application_sets_applied_at(auth_client, user, job, profile_set):
    response = auth_client.post(
        "/api/applications/",
        {"job_id": job.id, "status": "applied", "profile_set": profile_set.id, "note": "через HR"},
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["status"] == "applied"
    assert response.data["applied_at"] is not None
    assert response.data["profile_set_name"] == "Frontend RU"
    assert response.data["job"]["id"] == job.id
    assert Application.objects.get(user=user, job=job).note == "через HR"


@pytest.mark.django_db
def test_saved_status_has_no_applied_at(auth_client, job):
    response = auth_client.post("/api/applications/", {"job_id": job.id, "status": "saved"}, format="json")
    assert response.status_code == 201
    assert response.data["applied_at"] is None


@pytest.mark.django_db
def test_repeat_post_updates_existing_application(auth_client, user, job):
    auth_client.post("/api/applications/", {"job_id": job.id, "status": "saved"}, format="json")
    response = auth_client.post("/api/applications/", {"job_id": job.id, "status": "applied"}, format="json")
    assert response.status_code == 201
    assert Application.objects.filter(user=user, job=job).count() == 1
    assert Application.objects.get(user=user, job=job).status == "applied"
    assert Application.objects.get(user=user, job=job).applied_at is not None


@pytest.mark.django_db
def test_patch_status_and_note(auth_client, user, job):
    created = auth_client.post("/api/applications/", {"job_id": job.id, "status": "applied"}, format="json")
    response = auth_client.patch(
        f"/api/applications/{created.data['id']}/", {"status": "interview", "note": "в пятницу"}, format="json"
    )
    assert response.status_code == 200
    assert response.data["status"] == "interview"
    assert response.data["note"] == "в пятницу"


@pytest.mark.django_db
def test_cannot_use_other_users_profile_set(auth_client, other_user, job):
    foreign = ProfileSet.objects.create(user=other_user, name="Not mine", resume=_pdf_file())
    response = auth_client.post(
        "/api/applications/",
        {"job_id": job.id, "status": "applied", "profile_set": foreign.id},
        format="json",
    )
    assert response.status_code == 400
    assert Application.objects.count() == 0


@pytest.mark.django_db
def test_list_is_scoped_to_user_and_filterable(auth_client, user, other_user, job):
    Application.objects.create(user=user, job=job, status="applied")
    Application.objects.create(user=other_user, job=job, status="offer")

    response = auth_client.get("/api/applications/")
    assert response.status_code == 200
    assert [row["status"] for row in response.data] == ["applied"]

    assert auth_client.get("/api/applications/?status=offer").data == []
    assert len(auth_client.get(f"/api/applications/?job={job.id}").data) == 1


@pytest.mark.django_db
def test_cannot_access_other_users_application(auth_client, other_user, job):
    foreign = Application.objects.create(user=other_user, job=job, status="applied")
    assert auth_client.get(f"/api/applications/{foreign.id}/").status_code == 404
    assert auth_client.delete(f"/api/applications/{foreign.id}/").status_code == 404


@pytest.mark.django_db
def test_delete_application(auth_client, user, job):
    application = Application.objects.create(user=user, job=job, status="applied")
    assert auth_client.delete(f"/api/applications/{application.id}/").status_code == 204
    assert not Application.objects.filter(id=application.id).exists()


@pytest.mark.django_db
def test_deleting_profile_set_keeps_application(auth_client, user, job, profile_set):
    application = Application.objects.create(user=user, job=job, status="applied", profile_set=profile_set)
    profile_set.delete()
    application.refresh_from_db()
    assert application.profile_set is None


@pytest.mark.django_db
def test_job_list_exposes_application_status(auth_client, user, job):
    assert auth_client.get("/api/jobs/").data["results"][0]["application_status"] is None
    Application.objects.create(user=user, job=job, status="interview")
    assert auth_client.get("/api/jobs/").data["results"][0]["application_status"] == "interview"


@pytest.mark.django_db
def test_requires_auth(api_client):
    assert api_client.get("/api/applications/").status_code == 401
