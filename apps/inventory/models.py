"""
Inventory models: InventoryItem and InventoryTransaction (Audit Stock Ledger).
"""

from django.db import models
from apps.common.models import TimeStampedModel


class InventoryItem(TimeStampedModel):
    """
    Inventory item tracking current on-hand and reserved quantities for a product SKU.
    Enforces non-negative stock constraints at the database level.
    """
    variant = models.OneToOneField(
        "catalog.ProductVariant",
        on_delete=models.CASCADE,
        related_name="inventory",
    )
    quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Inventory Item"
        verbose_name_plural = "Inventory Items"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="inventory_quantity_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_quantity__gte=0),
                name="inventory_reserved_quantity_non_negative",
            ),
        ]

    @property
    def available_quantity(self) -> int:
        """
        Quantity available for purchase (on-hand minus reserved).
        """
        return max(0, self.quantity - self.reserved_quantity)

    @property
    def is_in_stock(self) -> bool:
        """
        Returns True if available quantity is strictly greater than 0.
        """
        return self.available_quantity > 0

    def __str__(self) -> str:
        return f"Inventory for {self.variant.sku}: {self.quantity} on hand ({self.reserved_quantity} reserved)"


class InventoryTransaction(models.Model):
    """
    Immutable audit ledger recording every change in inventory quantity.
    Provides complete historical tracking of restocks, sales deductions, returns, and manual adjustments.
    """
    class TransactionType(models.TextChoices):
        PURCHASE_DEDUCTION = "PURCHASE_DEDUCTION", "Purchase Deduction"
        RESTOCK = "RESTOCK", "Restock"
        REFUND_RETURN = "REFUND_RETURN", "Refund Return"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"

    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    transaction_type = models.CharField(
        max_length=30,
        choices=TransactionType.choices,
        db_index=True,
    )
    quantity_delta = models.IntegerField(
        help_text="Change in quantity (positive for additions, negative for deductions)."
    )
    balance_after = models.IntegerField(
        help_text="Snapshot of inventory quantity immediately following this transaction."
    )
    reference_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="External identifier such as Order ID, Cart ID, or Restock PO.",
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Inventory Transaction"
        verbose_name_plural = "Inventory Transactions"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return (
            f"{self.transaction_type} ({self.quantity_delta:+d}) for "
            f"{self.inventory_item.variant.sku} -> Balance: {self.balance_after}"
        )
