"""
Catalog serializers for DRF views.
"""

from rest_framework import serializers

from apps.catalog.models import Category, Product, ProductVariant


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for product categories.
    """
    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class ProductVariantSerializer(serializers.ModelSerializer):
    """
    Serializer for product variants (SKUs), including effective price and live stock availability.
    """
    effective_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    stock_quantity = serializers.SerializerMethodField()
    is_in_stock = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "variant_name",
            "price_override",
            "effective_price",
            "is_active",
            "stock_quantity",
            "is_in_stock",
            "created_at",
        ]
        read_only_fields = fields

    def get_stock_quantity(self, obj: ProductVariant) -> int:
        if hasattr(obj, "inventory") and obj.inventory is not None:
            return obj.inventory.available_quantity
        return 0

    def get_is_in_stock(self, obj: ProductVariant) -> bool:
        if hasattr(obj, "inventory") and obj.inventory is not None:
            return obj.inventory.is_in_stock
        return False


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for products including nested category and variants.
    """
    category = CategorySerializer(read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "base_price",
            "is_active",
            "category",
            "variants",
            "created_at",
        ]
        read_only_fields = fields
