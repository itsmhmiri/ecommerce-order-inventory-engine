"""
Unit tests for user registration and authentication serializers.
"""

import pytest
from django.contrib.auth import get_user_model

from apps.authentication.serializers import UserRegisterSerializer, UserSerializer

User = get_user_model()


@pytest.mark.django_db
class TestUserRegisterSerializer:
    def test_valid_registration_serializer(self):
        payload = {
            "username": "newshopper",
            "email": "newshopper@example.com",
            "password": "StrongPassword123!",
            "first_name": "Jane",
            "last_name": "Doe",
        }
        serializer = UserRegisterSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors

        user = serializer.save()
        assert user.username == "newshopper"
        assert user.email == "newshopper@example.com"
        assert user.first_name == "Jane"
        assert user.last_name == "Doe"
        assert user.check_password("StrongPassword123!")

    def test_duplicate_username_fails(self):
        User.objects.create_user(username="existing", email="existing@example.com", password="password123")
        payload = {
            "username": "existing",
            "email": "different@example.com",
            "password": "StrongPassword123!",
        }
        serializer = UserRegisterSerializer(data=payload)
        assert not serializer.is_valid()
        assert "username" in serializer.errors

    def test_duplicate_email_fails(self):
        User.objects.create_user(username="existing1", email="taken@example.com", password="password123")
        payload = {
            "username": "newuser",
            "email": "TAKEN@example.com",
            "password": "StrongPassword123!",
        }
        serializer = UserRegisterSerializer(data=payload)
        assert not serializer.is_valid()
        assert "email" in serializer.errors

    def test_missing_required_fields_fails(self):
        serializer = UserRegisterSerializer(data={})
        assert not serializer.is_valid()
        assert "username" in serializer.errors
        assert "email" in serializer.errors
        assert "password" in serializer.errors


@pytest.mark.django_db
class TestUserSerializer:
    def test_user_serializer_output(self):
        user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="password123",
            first_name="Alice",
            last_name="Smith",
        )
        serializer = UserSerializer(user)
        assert serializer.data["id"] == user.id
        assert serializer.data["username"] == "testuser"
        assert serializer.data["email"] == "testuser@example.com"
        assert serializer.data["first_name"] == "Alice"
        assert serializer.data["last_name"] == "Smith"
        assert "password" not in serializer.data
