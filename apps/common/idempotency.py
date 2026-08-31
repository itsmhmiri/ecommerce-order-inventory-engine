"""
Idempotency utility and decorator for DRF API endpoints.
Provides database-backed idempotency guarantees using the Idempotency-Key HTTP header.
"""

import functools
import hashlib
import json
from typing import Any, Callable

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.response import Response

from apps.common.models import IdempotencyKey


def compute_request_hash(data: Any, path: str = "") -> str:
    """
    Computes a deterministic SHA-256 hash of the request payload and path.
    """
    try:
        serialized = json.dumps(data, sort_keys=True, default=str)
    except Exception:
        serialized = str(data)

    payload = f"{path}:{serialized}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def idempotent_request(func: Callable) -> Callable:
    """
    Decorator for DRF API view methods (e.g. POST) to ensure idempotent execution.

    Behavior:
      - If 'Idempotency-Key' header is missing or user is unauthenticated, executes normally.
      - If an existing completed key is found with matching payload hash, returns the cached response.
      - If an existing key with different payload hash is found, returns 422 Unprocessable Entity.
      - If an identical request is currently in progress, returns 409 Conflict.
      - Otherwise, marks the key IN_PROGRESS, executes the handler, caches the response, and marks COMPLETED.
    """

    @functools.wraps(func)
    def wrapper(view_instance: Any, request: Any, *args: Any, **kwargs: Any) -> Response:
        idempotency_header = (
            request.headers.get("Idempotency-Key") or request.META.get("HTTP_IDEMPOTENCY_KEY", "")
        ).strip()

        # Pass through if no key provided or user is not authenticated
        if not idempotency_header or not getattr(request, "user", None) or not request.user.is_authenticated:
            return func(view_instance, request, *args, **kwargs)

        request_hash = compute_request_hash(request.data, request.path)
        user = request.user

        # 1. Check or register idempotency key atomically
        key_record = None
        try:
            with transaction.atomic():
                existing = IdempotencyKey.objects.select_for_update().filter(user=user, key=idempotency_header).first()

                if existing:
                    if existing.status == IdempotencyKey.Status.COMPLETED:
                        if existing.request_hash != request_hash:
                            return Response(
                                {
                                    "detail": "Idempotency key payload mismatch. "
                                    "The request body does not match the original request for this key."
                                },
                                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            )
                        return Response(
                            data=existing.response_body,
                            status=existing.response_code or status.HTTP_200_OK,
                        )

                    if existing.status == IdempotencyKey.Status.IN_PROGRESS:
                        return Response(
                            {"detail": "A request with this Idempotency-Key is currently being processed."},
                            status=status.HTTP_409_CONFLICT,
                        )

                    # If previous attempt failed, allow retry by updating back to IN_PROGRESS
                    existing.status = IdempotencyKey.Status.IN_PROGRESS
                    existing.request_hash = request_hash
                    existing.request_path = request.path
                    existing.save(update_fields=["status", "request_hash", "request_path", "updated_at"])
                    key_record = existing
                else:
                    key_record = IdempotencyKey.objects.create(
                        user=user,
                        key=idempotency_header,
                        request_path=request.path,
                        request_hash=request_hash,
                        status=IdempotencyKey.Status.IN_PROGRESS,
                    )
        except IntegrityError:
            # Handle race condition where another thread created the key simultaneously
            return Response(
                {"detail": "A request with this Idempotency-Key is currently being processed."},
                status=status.HTTP_409_CONFLICT,
            )

        # 2. Execute the underlying view handler
        try:
            response = func(view_instance, request, *args, **kwargs)
        except Exception:
            # On unhandled error, mark key as FAILED to allow clean retries
            try:
                key_record.status = IdempotencyKey.Status.FAILED
                key_record.save(update_fields=["status", "updated_at"])
            except Exception:
                pass
            raise

        # 3. Cache successful or client-error responses
        try:
            key_record.status = IdempotencyKey.Status.COMPLETED
            key_record.response_code = response.status_code
            key_record.response_body = getattr(response, "data", None)
            key_record.save(update_fields=["status", "response_code", "response_body", "updated_at"])
        except Exception:
            pass

        return response

    return wrapper
