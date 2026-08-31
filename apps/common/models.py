import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """
    Abstract base model with created_at and updated_at timestamps.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(TimeStampedModel):
    """
    Abstract model with UUID primary key and timestamps.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class IdempotencyKey(TimeStampedModel):
    """
    Database-backed idempotency key storage.
    Tracks in-flight requests and caches responses for safe API retries without duplicate side-effects.
    """

    class Status(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="idempotency_keys",
    )
    key = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Unique client-supplied idempotency key (e.g. UUID header).",
    )
    request_path = models.CharField(max_length=255)
    request_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of the request body and parameters.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
        db_index=True,
    )
    response_code = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="HTTP response status code returned by the operation.",
    )
    response_body = models.JSONField(
        null=True,
        blank=True,
        help_text="Cached serialized JSON response body.",
    )

    class Meta:
        verbose_name = "Idempotency Key"
        verbose_name_plural = "Idempotency Keys"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "key"],
                name="unique_user_idempotency_key",
            )
        ]

    def __str__(self) -> str:
        return f"IdempotencyKey({self.key}) for {self.user.username} [{self.status}]"
