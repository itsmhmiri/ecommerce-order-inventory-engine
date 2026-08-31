"""
Inventory serializers for DRF views.
"""

from rest_framework import serializers

from apps.inventory.models import InventoryItem, InventoryTransaction


class InventoryItemSerializer(serializers.ModelSerializer):
    """
    Serializer for inventory items.
    """

    variant_sku = serializers.CharField(source="variant.sku", read_only=True)
    available_quantity = serializers.IntegerField(read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            "id",
            "variant",
            "variant_sku",
            "quantity",
            "reserved_quantity",
            "available_quantity",
            "is_in_stock",
            "updated_at",
            "created_at",
        ]
        read_only_fields = fields


class InventoryTransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for immutable stock ledger transactions.
    """

    variant_sku = serializers.CharField(source="inventory_item.variant.sku", read_only=True)
    product_title = serializers.CharField(source="inventory_item.variant.product.title", read_only=True)

    class Meta:
        model = InventoryTransaction
        fields = [
            "id",
            "inventory_item",
            "variant_sku",
            "product_title",
            "transaction_type",
            "quantity_delta",
            "balance_after",
            "reference_id",
            "notes",
            "created_at",
        ]
        read_only_fields = fields
