"""
Django admin configuration for inventory models.
"""

from django.contrib import admin
from apps.inventory.models import InventoryItem, InventoryTransaction


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ["variant", "quantity", "reserved_quantity", "available_quantity", "is_in_stock", "updated_at"]
    search_fields = ["variant__sku", "variant__product__title"]
    readonly_fields = ["available_quantity", "is_in_stock", "created_at", "updated_at"]


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "inventory_item",
        "transaction_type",
        "quantity_delta",
        "balance_after",
        "reference_id",
    ]
    list_filter = ["transaction_type", "created_at"]
    search_fields = ["inventory_item__variant__sku", "reference_id", "notes"]
    readonly_fields = [
        "inventory_item",
        "transaction_type",
        "quantity_delta",
        "balance_after",
        "reference_id",
        "notes",
        "created_at",
    ]

    def has_add_permission(self, request):
        # Audit ledger entries should only be created via service layer or system events
        return False

    def has_delete_permission(self, request, obj=None):
        # Audit ledger must be immutable
        return False
