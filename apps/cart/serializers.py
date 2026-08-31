"""
Cart serializers for DRF API views and payload validation.
"""

from rest_framework import serializers
from apps.catalog.models import ProductVariant
from apps.cart.models import Cart, CartItem


class CartItemVariantSerializer(serializers.ModelSerializer):
    """
    Nested serializer for variant information within a cart item.
    """
    product_title = serializers.CharField(source="product.title", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    available_stock = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "variant_name",
            "product_title",
            "product_slug",
            "effective_price",
            "available_stock",
        ]
        read_only_fields = fields

    def get_available_stock(self, obj: ProductVariant) -> int:
        if hasattr(obj, "inventory") and obj.inventory is not None:
            return obj.inventory.available_quantity
        return 0


class CartItemSerializer(serializers.ModelSerializer):
    """
    Output serializer for cart line items.
    """
    variant = CartItemVariantSerializer(read_only=True)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = [
            "id",
            "variant",
            "quantity",
            "unit_price",
            "subtotal",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AddCartItemInputSerializer(serializers.Serializer):
    """
    Input serializer for adding an item to the shopping cart.
    """
    variant_id = serializers.IntegerField(
        required=True,
        help_text="Primary key of the ProductVariant SKU to add.",
    )
    quantity = serializers.IntegerField(
        default=1,
        min_value=1,
        help_text="Quantity to add to the cart (must be at least 1).",
    )

    def validate_variant_id(self, value: int) -> int:
        variant = ProductVariant.objects.filter(id=value).first()
        if variant is None:
            raise serializers.ValidationError(f"ProductVariant with ID {value} does not exist.")
        if not variant.is_active:
            raise serializers.ValidationError(f"ProductVariant with SKU '{variant.sku}' is inactive.")
        return value


class UpdateCartItemInputSerializer(serializers.Serializer):
    """
    Input serializer for updating quantity of an existing cart item.
    """
    quantity = serializers.IntegerField(
        required=True,
        min_value=1,
        help_text="New positive quantity for the cart item.",
    )


class CartSerializer(serializers.ModelSerializer):
    """
    Output serializer representing the complete shopping cart and itemized breakdown.
    """
    user_id = serializers.IntegerField(source="user.id", read_only=True, allow_null=True)
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = [
            "id",
            "user_id",
            "items",
            "total_items",
            "total_price",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
