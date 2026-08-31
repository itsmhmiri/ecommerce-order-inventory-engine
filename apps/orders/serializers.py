"""
Order serializers for DRF API views and checkout payload validation.
"""

from rest_framework import serializers
from apps.orders.models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Serializer for order line items with immutable historical price and SKU snapshot fields.
    """
    variant_id = serializers.IntegerField(source="variant.id", read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "variant_id",
            "sku",
            "product_title",
            "unit_price",
            "quantity",
            "subtotal",
        ]
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    """
    Output serializer for full Order details with itemized snapshot lines.
    """
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "user_id",
            "status",
            "total_amount",
            "shipping_address",
            "items",
            "total_items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CheckoutInputSerializer(serializers.Serializer):
    """
    Input serializer for cart checkout.
    """
    shipping_address = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Shipping delivery address for the order.",
    )
