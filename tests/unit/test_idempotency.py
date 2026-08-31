"""
Unit tests for IdempotencyKey domain model, hashing utility, and @idempotent_request decorator.
"""

from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response

from apps.common.idempotency import compute_request_hash, idempotent_request
from apps.common.models import IdempotencyKey

User = get_user_model()


@pytest.fixture
def idempotency_user(db):
    return User.objects.create_user(username="idemp_user", password="password123")


@pytest.mark.django_db
class TestIdempotencyKeyModel:
    def test_create_idempotency_key(self, idempotency_user):
        record = IdempotencyKey.objects.create(
            user=idempotency_user,
            key="test-key-uuid-001",
            request_path="/api/v1/orders/checkout/",
            request_hash="mockhash1234567890",
            status=IdempotencyKey.Status.IN_PROGRESS,
        )
        assert record.id is not None
        assert record.status == IdempotencyKey.Status.IN_PROGRESS
        assert record.response_code is None
        assert record.response_body is None
        assert "test-key-uuid-001" in str(record)

    def test_unique_user_key_constraint(self, idempotency_user):
        IdempotencyKey.objects.create(
            user=idempotency_user,
            key="duplicate-key",
            request_path="/api/v1/orders/checkout/",
            request_hash="hash1",
        )
        with pytest.raises(IntegrityError):
            IdempotencyKey.objects.create(
                user=idempotency_user,
                key="duplicate-key",
                request_path="/api/v1/orders/checkout/",
                request_hash="hash2",
            )


class TestComputeRequestHash:
    def test_deterministic_hash(self):
        data1 = {"b": 2, "a": 1}
        data2 = {"a": 1, "b": 2}
        assert compute_request_hash(data1, "/path") == compute_request_hash(data2, "/path")

    def test_different_paths_produce_different_hashes(self):
        data = {"key": "value"}
        assert compute_request_hash(data, "/path1") != compute_request_hash(data, "/path2")


@pytest.mark.django_db
class TestIdempotentRequestDecorator:
    def test_passthrough_when_no_key_header(self, idempotency_user):
        called = False

        class DummyView:
            @idempotent_request
            def post(self, request):
                nonlocal called
                called = True
                return Response({"ok": True}, status=status.HTTP_200_OK)

        mock_request = Mock()
        mock_request.headers = {}
        mock_request.META = {}
        mock_request.user = idempotency_user
        mock_request.data = {}
        mock_request.path = "/test/"

        view = DummyView()
        response = view.post(mock_request)
        assert called is True
        assert response.status_code == status.HTTP_200_OK
        assert IdempotencyKey.objects.count() == 0

    def test_passthrough_when_user_unauthenticated(self):
        class DummyView:
            @idempotent_request
            def post(self, request):
                return Response({"ok": True}, status=status.HTTP_200_OK)

        mock_request = Mock()
        mock_request.headers = {"Idempotency-Key": "some-key"}
        mock_request.META = {}
        mock_request.user = None
        mock_request.data = {}
        mock_request.path = "/test/"

        view = DummyView()
        response = view.post(mock_request)
        assert response.status_code == status.HTTP_200_OK
        assert IdempotencyKey.objects.count() == 0

    def test_first_call_creates_key_and_caches_response(self, idempotency_user):
        class DummyView:
            @idempotent_request
            def post(self, request):
                return Response({"order_id": "123"}, status=status.HTTP_201_CREATED)

        mock_request = Mock()
        mock_request.headers = {"Idempotency-Key": "key-001"}
        mock_request.META = {}
        mock_request.user = idempotency_user
        mock_request.data = {"shipping_address": "123 Main St"}
        mock_request.path = "/api/v1/orders/checkout/"

        view = DummyView()
        response = view.post(mock_request)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data == {"order_id": "123"}

        key_record = IdempotencyKey.objects.get(user=idempotency_user, key="key-001")
        assert key_record.status == IdempotencyKey.Status.COMPLETED
        assert key_record.response_code == 201
        assert key_record.response_body == {"order_id": "123"}

    def test_subsequent_call_returns_cached_response(self, idempotency_user):
        call_count = 0

        class DummyView:
            @idempotent_request
            def post(self, request):
                nonlocal call_count
                call_count += 1
                return Response({"order_id": "first-order"}, status=status.HTTP_201_CREATED)

        mock_request = Mock()
        mock_request.headers = {"Idempotency-Key": "key-002"}
        mock_request.META = {}
        mock_request.user = idempotency_user
        mock_request.data = {"items": [1, 2]}
        mock_request.path = "/checkout/"

        view = DummyView()
        res1 = view.post(mock_request)
        res2 = view.post(mock_request)

        assert call_count == 1
        assert res1.status_code == status.HTTP_201_CREATED
        assert res2.status_code == status.HTTP_201_CREATED
        assert res2.data == {"order_id": "first-order"}

    def test_call_with_different_payload_returns_422(self, idempotency_user):
        class DummyView:
            @idempotent_request
            def post(self, request):
                return Response({"order_id": "123"}, status=status.HTTP_201_CREATED)

        mock_request1 = Mock()
        mock_request1.headers = {"Idempotency-Key": "key-003"}
        mock_request1.META = {}
        mock_request1.user = idempotency_user
        mock_request1.data = {"shipping_address": "Address 1"}
        mock_request1.path = "/checkout/"

        mock_request2 = Mock()
        mock_request2.headers = {"Idempotency-Key": "key-003"}
        mock_request2.META = {}
        mock_request2.user = idempotency_user
        mock_request2.data = {"shipping_address": "Different Address"}
        mock_request2.path = "/checkout/"

        view = DummyView()
        res1 = view.post(mock_request1)
        res2 = view.post(mock_request2)

        assert res1.status_code == status.HTTP_201_CREATED
        assert res2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "mismatch" in res2.data["detail"].lower()

    def test_in_progress_key_returns_409(self, idempotency_user):
        # Manually create key in IN_PROGRESS state
        hash_val = compute_request_hash({"test": "data"}, "/checkout/")
        IdempotencyKey.objects.create(
            user=idempotency_user,
            key="key-in-flight",
            request_path="/checkout/",
            request_hash=hash_val,
            status=IdempotencyKey.Status.IN_PROGRESS,
        )

        class DummyView:
            @idempotent_request
            def post(self, request):
                return Response({"done": True}, status=status.HTTP_200_OK)

        mock_request = Mock()
        mock_request.headers = {"Idempotency-Key": "key-in-flight"}
        mock_request.META = {}
        mock_request.user = idempotency_user
        mock_request.data = {"test": "data"}
        mock_request.path = "/checkout/"

        view = DummyView()
        response = view.post(mock_request)
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "currently being processed" in response.data["detail"]

    def test_failed_key_allows_retry_and_recovers(self, idempotency_user):
        # Create previously failed key
        hash_val = compute_request_hash({"retry": True}, "/checkout/")
        IdempotencyKey.objects.create(
            user=idempotency_user,
            key="key-failed",
            request_path="/checkout/",
            request_hash=hash_val,
            status=IdempotencyKey.Status.FAILED,
        )

        class DummyView:
            @idempotent_request
            def post(self, request):
                return Response({"recovered": True}, status=status.HTTP_200_OK)

        mock_request = Mock()
        mock_request.headers = {"Idempotency-Key": "key-failed"}
        mock_request.META = {}
        mock_request.user = idempotency_user
        mock_request.data = {"retry": True}
        mock_request.path = "/checkout/"

        view = DummyView()
        response = view.post(mock_request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"recovered": True}

        key_record = IdempotencyKey.objects.get(user=idempotency_user, key="key-failed")
        assert key_record.status == IdempotencyKey.Status.COMPLETED

    def test_exception_in_view_marks_key_failed(self, idempotency_user):
        class DummyView:
            @idempotent_request
            def post(self, request):
                raise RuntimeError("Unexpected boom")

        mock_request = Mock()
        mock_request.headers = {"Idempotency-Key": "key-boom"}
        mock_request.META = {}
        mock_request.user = idempotency_user
        mock_request.data = {}
        mock_request.path = "/test/"

        view = DummyView()
        with pytest.raises(RuntimeError):
            view.post(mock_request)

        key_record = IdempotencyKey.objects.get(user=idempotency_user, key="key-boom")
        assert key_record.status == IdempotencyKey.Status.FAILED

    def test_compute_hash_non_serializable(self):
        class CustomObj:
            def __str__(self):
                return "custom_str"

        h1 = compute_request_hash(CustomObj(), "/path")
        assert len(h1) == 64

    def test_integrity_error_race_returns_409(self, idempotency_user, monkeypatch):

        def mock_create(*args, **kwargs):
            raise IntegrityError("duplicate key")

        monkeypatch.setattr(IdempotencyKey.objects, "create", mock_create)

        class DummyView:
            @idempotent_request
            def post(self, request):
                return Response({"ok": True})

        mock_request = Mock()
        mock_request.headers = {"Idempotency-Key": "race-key"}
        mock_request.META = {}
        mock_request.user = idempotency_user
        mock_request.data = {}
        mock_request.path = "/test/"

        view = DummyView()
        response = view.post(mock_request)
        assert response.status_code == status.HTTP_409_CONFLICT
