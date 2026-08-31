"""
Order domain models: Order and OrderItem (with historical price and SKU snapshots).
"""

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.common.models import UUIDModel


class Order(UUIDModel):
    """
    Customer order entity representing a committed purchase.
    Tracks financial amount, fulfillment status, and customer shipping address.
    """

    class OrderStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        PAID = "PAID", "Paid"
        CANCELLED = "CANCELLED", "Cancelled"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    shipping_address = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ["-created_at"]

    @property
    def total_items(self) -> int:
        """
        Total quantity of all items in the order.
        """
        return sum(item.quantity for item in self.items.all())

    def __str__(self) -> str:
        return f"Order {self.id} ({self.status}) - User: {self.user.username}"


class OrderItem(models.Model):
    """
    Individual line item in an Order.
    Stores immutable historical snapshots of product title, SKU, and unit price
    at the time of purchase to safeguard against future catalog price/title changes.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    sku = models.CharField(
        max_length=100,
        help_text="Historical snapshot of SKU at time of order.",
    )
    product_title = models.CharField(
        max_length=255,
        help_text="Historical snapshot of Product title at time of order.",
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Historical snapshot of unit price at time of order.",
    )
    quantity = models.PositiveIntegerField(default=1)
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Line item subtotal (unit_price * quantity).",
    )

    class Meta:
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.quantity}x {self.sku} (${self.unit_price}) in Order {self.order_id}"
