"""
Pytest global fixtures for E-Commerce Order & Inventory Engine.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def auth_user(db):
    return User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="securepassword123",
    )

@pytest.fixture
def authenticated_client(api_client, auth_user):
    api_client.force_authenticate(user=auth_user)
    return api_client
