"""
Idempotency key Django Admin configuration.
"""

from django.contrib import admin

from apps.common.models import IdempotencyKey


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "key", "request_path", "status", "response_code", "created_at"]
    list_filter = ["status", "response_code", "created_at"]
    search_fields = ["id", "key", "user__username", "user__email", "request_path", "request_hash"]
    readonly_fields = [
        "id",
        "user",
        "key",
        "request_path",
        "request_hash",
        "status",
        "response_code",
        "response_body",
        "created_at",
        "updated_at",
    ]
