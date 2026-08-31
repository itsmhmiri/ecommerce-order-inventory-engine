"""
Stock service layer: Business logic for inventory adjustments and stock audit ledgers.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.catalog.models import ProductVariant
from apps.inventory.models import InventoryItem, InventoryTransaction


class InsufficientStockError(ValidationError):
    """
    Raised when an operation would cause inventory to drop below zero.
    """


class StockService:
    """
    Service responsible for mutating inventory and ensuring an immutable audit ledger entry
    is created for every stock movement.
    """

    @classmethod
    def adjust_stock(
        cls,
        *,
        variant: ProductVariant,
        delta: int,
        transaction_type: str = InventoryTransaction.TransactionType.ADJUSTMENT,
        reference_id: str = "",
        notes: str = "",
    ) -> InventoryTransaction:
        """
        Atomically adjusts the stock for a given SKU variant using row-level pessimistic locking.
        Creates an audit ledger entry in InventoryTransaction with the new balance.

        Args:
            variant: ProductVariant instance whose stock is changing.
            delta: Quantity delta (positive for additions, negative for deductions).
            transaction_type: Transaction classification (RESTOCK, PURCHASE_DEDUCTION, etc.).
            reference_id: Identifier of related entity (e.g. Order ID, PO number).
            notes: Human-readable explanation.

        Returns:
            InventoryTransaction: Created ledger entry.

        Raises:
            InsufficientStockError: If the deduction exceeds available stock.
        """
        with transaction.atomic():
            # Acquire row-level lock on the InventoryItem
            inventory, _ = InventoryItem.objects.select_for_update().get_or_create(
                variant=variant,
                defaults={"quantity": 0, "reserved_quantity": 0},
            )

            new_quantity = inventory.quantity + delta
            if new_quantity < 0:
                raise InsufficientStockError(
                    f"Insufficient stock for SKU '{variant.sku}'. "
                    f"Current stock: {inventory.quantity}, requested change: {delta}."
                )

            inventory.quantity = new_quantity
            inventory.save(update_fields=["quantity", "updated_at"])

            ledger_entry = InventoryTransaction.objects.create(
                inventory_item=inventory,
                transaction_type=transaction_type,
                quantity_delta=delta,
                balance_after=new_quantity,
                reference_id=reference_id,
                notes=notes,
            )

            return ledger_entry

    @classmethod
    def restock(
        cls,
        *,
        variant: ProductVariant,
        quantity: int,
        reference_id: str = "",
        notes: str = "Restock shipment received",
    ) -> InventoryTransaction:
        """
        Convenience method to add stock to an SKU variant.
        """
        if quantity <= 0:
            raise ValidationError("Restock quantity must be strictly positive.")
        return cls.adjust_stock(
            variant=variant,
            delta=quantity,
            transaction_type=InventoryTransaction.TransactionType.RESTOCK,
            reference_id=reference_id,
            notes=notes,
        )

    @classmethod
    def deduct_stock(
        cls,
        *,
        variant: ProductVariant,
        quantity: int,
        transaction_type: str = InventoryTransaction.TransactionType.PURCHASE_DEDUCTION,
        reference_id: str = "",
        notes: str = "Purchase deduction",
    ) -> InventoryTransaction:
        """
        Convenience method to deduct stock from an SKU variant.
        """
        if quantity <= 0:
            raise ValidationError("Deduct quantity must be strictly positive.")
        return cls.adjust_stock(
            variant=variant,
            delta=-quantity,
            transaction_type=transaction_type,
            reference_id=reference_id,
            notes=notes,
        )
