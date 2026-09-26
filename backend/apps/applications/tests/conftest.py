import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Customer


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db) -> Customer:
    return Customer.objects.create_user(username="alice", password="pass12345")


@pytest.fixture
def other_user(db) -> Customer:
    return Customer.objects.create_user(username="bob", password="pass12345")


@pytest.fixture
def auth_client(api_client: APIClient, user: Customer) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client
