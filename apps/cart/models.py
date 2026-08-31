"""
Cart domain models: Cart and CartItem.
"""

from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel, UUIDModel


class Cart(UUIDModel):
    """
    Shopping cart representing a customer's active selection of items.
    Supports authenticated users and guest sessions.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="carts",
    )

    class Meta:
        verbose_name = "Cart"
        verbose_name_plural = "Carts"
        ordering = ["-created_at"]

    @property
    def total_items(self) -> int:
        """
        Total quantity of all items in the cart.
        """
        return sum(item.quantity for item in self.items.all())

    @property
    def total_price(self) -> Decimal:
        """
        Total monetary amount of all items in the cart.
        """
        return sum(
            (item.subtotal for item in self.items.all()),
            Decimal("0.00"),
        )

    @property
    def is_empty(self) -> bool:
        """
        Returns True if the cart contains no items.
        """
        return not self.items.exists()

    def __str__(self) -> str:
        owner = self.user.username if self.user else "Guest"
        return f"Cart {self.id} ({owner})"


class CartItem(TimeStampedModel):
    """
    Line item inside a shopping cart referencing a specific product variant SKU and quantity.
    """
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "variant"],
                name="unique_cart_variant",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="cart_item_quantity_positive",
            ),
        ]

    @property
    def unit_price(self) -> Decimal:
        """
        Effective unit price of the variant at the current time.
        """
        return self.variant.effective_price

    @property
    def subtotal(self) -> Decimal:
        """
        Calculated subtotal for this line item (unit_price * quantity).
        """
        return self.unit_price * self.quantity

    def __str__(self) -> str:
        return f"{self.quantity}x {self.variant.sku} (Cart {self.cart_id})"
