"""
Integration tests for authentication API endpoints: registration and JWT tokens.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

User = get_user_model()


@pytest.mark.django_db
class TestAuthAPI:
    def test_register_user_success(self, api_client):
        url = "/api/v1/auth/register/"
        payload = {
            "username": "customer1",
            "email": "customer1@example.com",
            "password": "SuperSecretPassword123!",
            "first_name": "John",
            "last_name": "Doe",
        }
        response = api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["username"] == "customer1"
        assert response.data["email"] == "customer1@example.com"
        assert response.data["first_name"] == "John"
        assert response.data["last_name"] == "Doe"
        assert "password" not in response.data

        # Verify user is in database
        user = User.objects.get(username="customer1")
        assert user.check_password("SuperSecretPassword123!")

    def test_register_user_duplicate_username_fails(self, api_client):
        User.objects.create_user(username="customer1", email="c1@example.com", password="password123")
        url = "/api/v1/auth/register/"
        payload = {
            "username": "customer1",
            "email": "c2@example.com",
            "password": "SuperSecretPassword123!",
        }
        response = api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "username" in response.data

    def test_register_user_duplicate_email_fails(self, api_client):
        User.objects.create_user(username="customer1", email="duplicate@example.com", password="password123")
        url = "/api/v1/auth/register/"
        payload = {
            "username": "customer2",
            "email": "duplicate@example.com",
            "password": "SuperSecretPassword123!",
        }
        response = api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_obtain_jwt_token_and_refresh(self, api_client):
        User.objects.create_user(
            username="jwtuser",
            email="jwtuser@example.com",
            password="MySecretPassword123!",
        )

        # 1. Obtain token pair
        token_url = "/api/v1/auth/token/"
        response = api_client.post(
            token_url,
            {"username": "jwtuser", "password": "MySecretPassword123!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        refresh_token = response.data["refresh"]

        # 2. Refresh token
        refresh_url = "/api/v1/auth/token/refresh/"
        refresh_response = api_client.post(
            refresh_url,
            {"refresh": refresh_token},
            format="json",
        )
        assert refresh_response.status_code == status.HTTP_200_OK
        assert "access" in refresh_response.data
