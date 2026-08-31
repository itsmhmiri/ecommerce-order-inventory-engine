"""
Payment Django Admin configuration.
"""

from django.contrib import admin

from apps.payments.models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "order",
        "amount",
        "status",
        "simulated_gateway_ref",
        "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = [
        "id",
        "order__id",
        "simulated_gateway_ref",
        "error_message",
    ]
    readonly_fields = [
        "id",
        "order",
        "amount",
        "status",
        "simulated_gateway_ref",
        "error_message",
        "created_at",
        "updated_at",
    ]
