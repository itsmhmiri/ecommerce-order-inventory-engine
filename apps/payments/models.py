"""
Payment domain models: Simulated PaymentTransaction ledger.
"""

from decimal import Decimal

from django.db import models

from apps.common.models import UUIDModel


class PaymentTransaction(UUIDModel):
    """
    Simulated payment transaction entity representing a payment attempt for an Order.
    Tracks gateway references, financial amounts, transition statuses, and error messages.
    """

    class PaymentStatus(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payment_transaction",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Amount billed for this transaction.",
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.SUCCESS,
        db_index=True,
    )
    simulated_gateway_ref = models.CharField(
        max_length=100,
        unique=True,
        help_text="Deterministic or unique mock payment gateway reference ID.",
    )
    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Gateway decline reason or error description if payment failed.",
    )

    class Meta:
        verbose_name = "Payment Transaction"
        verbose_name_plural = "Payment Transactions"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Payment {self.simulated_gateway_ref} ({self.status}) for Order {self.order_id}"
