import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.profiles.models import ProfileSet, RESUME_MAX_SIZE_BYTES


def _pdf_file(name: str = "resume.pdf", size: int = 1024) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, b"%PDF-1.4 " + b"x" * size, content_type="application/pdf")


@pytest.mark.django_db
def test_create_profile_set(auth_client, user):
    response = auth_client.post(
        "/api/profile-sets/",
        {
            "name": "Frontend RU",
            "phone": "+79991234567",
            "email": "me@example.com",
            "github_url": "https://github.com/example",
            "resume": _pdf_file(),
        },
        format="multipart",
    )
    assert response.status_code == 201, response.data
    assert response.data["name"] == "Frontend RU"
    assert ProfileSet.objects.get(id=response.data["id"]).user == user


@pytest.mark.django_db
def test_list_only_returns_own_profile_sets(auth_client, user, other_user):
    ProfileSet.objects.create(user=user, name="Mine", resume=_pdf_file())
    ProfileSet.objects.create(user=other_user, name="Not mine", resume=_pdf_file())

    response = auth_client.get("/api/profile-sets/")
    assert response.status_code == 200
    names = {row["name"] for row in response.data["results"]}
    assert names == {"Mine"}


@pytest.mark.django_db
def test_cannot_access_another_users_profile_set(auth_client, other_user):
    other_set = ProfileSet.objects.create(user=other_user, name="Not mine", resume=_pdf_file())

    response = auth_client.get(f"/api/profile-sets/{other_set.id}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_update_profile_set_without_reuploading_resume(auth_client, user):
    profile_set = ProfileSet.objects.create(user=user, name="Old name", resume=_pdf_file())

    response = auth_client.patch(
        f"/api/profile-sets/{profile_set.id}/",
        {"name": "New name"},
        format="multipart",
    )
    assert response.status_code == 200
    profile_set.refresh_from_db()
    assert profile_set.name == "New name"
    assert profile_set.resume  # файл остался, не был затёрт пустым значением


@pytest.mark.django_db
def test_delete_profile_set(auth_client, user):
    profile_set = ProfileSet.objects.create(user=user, name="To delete", resume=_pdf_file())

    response = auth_client.delete(f"/api/profile-sets/{profile_set.id}/")
    assert response.status_code == 204
    assert not ProfileSet.objects.filter(id=profile_set.id).exists()


@pytest.mark.django_db
def test_rejects_non_resume_file_extension(auth_client):
    bad_file = SimpleUploadedFile("resume.exe", b"not a resume", content_type="application/octet-stream")
    response = auth_client.post(
        "/api/profile-sets/",
        {"name": "Bad file", "resume": bad_file},
        format="multipart",
    )
    assert response.status_code == 400
    assert "resume" in response.data


@pytest.mark.django_db
def test_rejects_oversized_resume(auth_client):
    too_big = _pdf_file(size=RESUME_MAX_SIZE_BYTES + 1)
    response = auth_client.post(
        "/api/profile-sets/",
        {"name": "Too big", "resume": too_big},
        format="multipart",
    )
    assert response.status_code == 400
    assert "resume" in response.data


@pytest.mark.django_db
def test_requires_authentication(api_client):
    response = api_client.get("/api/profile-sets/")
    assert response.status_code == 401
