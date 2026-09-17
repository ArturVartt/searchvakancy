import pytest
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import Customer


@pytest.mark.django_db
def test_register_creates_user_and_returns_working_token():
    client = APIClient()
    response = client.post(
        "/api/auth/register/", {"username": "newbie", "password": "correct-horse-battery-1"}
    )
    assert response.status_code == 201
    token = response.data["token"]

    user = Customer.objects.get(username="newbie")
    assert Token.objects.get(user=user).key == token
    assert user.check_password("correct-horse-battery-1")

    client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
    me = client.get("/api/jobs/filters/")
    assert me.status_code == 200


@pytest.mark.django_db
def test_register_rejects_weak_password():
    client = APIClient()
    response = client.post("/api/auth/register/", {"username": "weak", "password": "123"})
    assert response.status_code == 400
    assert not Customer.objects.filter(username="weak").exists()


@pytest.mark.django_db
def test_register_rejects_duplicate_username():
    Customer.objects.create_user(username="taken", password="whatever-strong-1")
    client = APIClient()
    response = client.post(
        "/api/auth/register/", {"username": "taken", "password": "another-strong-pass-1"}
    )
    assert response.status_code == 400
