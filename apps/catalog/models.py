"""
Catalog models: Category, Product, and ProductVariant (SKU).
"""

from decimal import Decimal

from django.db import models

from apps.common.models import TimeStampedModel


class Category(TimeStampedModel):
    """
    Product category model.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Product(TimeStampedModel):
    """
    Base product model containing general product information.
    """
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products",
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True, default="")
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class ProductVariant(TimeStampedModel):
    """
    Product variant (SKU) representing a specific purchasable option
    (e.g., specific size, color) with optional price override.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    variant_name = models.CharField(max_length=255)
    price_override = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["sku"]

    @property
    def effective_price(self) -> Decimal:
        """
        Returns price_override if set; otherwise falls back to the parent product's base_price.
        """
        if self.price_override is not None:
            return self.price_override
        return self.product.base_price

    def __str__(self) -> str:
        return f"{self.product.title} - {self.variant_name} ({self.sku})"
