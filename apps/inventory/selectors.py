"""
Inventory selectors: Read-only queries for stock and audit ledger transactions.
"""


from django.db.models import QuerySet

from apps.catalog.models import ProductVariant
from apps.inventory.models import InventoryItem, InventoryTransaction


def get_inventory_for_variant(variant: ProductVariant) -> InventoryItem | None:
    """
    Retrieves the inventory item for a given product variant.
    """
    return InventoryItem.objects.filter(variant=variant).first()


def list_inventory_transactions(
    *,
    variant_id: int | None = None,
    transaction_type: str | None = None,
) -> QuerySet[InventoryTransaction]:
    """
    Returns audit ledger transactions with optional filtering and prefetched relations.
    """
    qs = (
        InventoryTransaction.objects.select_related(
            "inventory_item",
            "inventory_item__variant",
            "inventory_item__variant__product",
        )
        .order_by("-created_at")
    )
    if variant_id is not None:
        qs = qs.filter(inventory_item__variant_id=variant_id)
    if transaction_type:
        qs = qs.filter(transaction_type=transaction_type)
    return qs
