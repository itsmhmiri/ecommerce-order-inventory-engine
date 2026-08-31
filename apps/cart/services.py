"""
Cart service layer: Business logic for managing shopping cart items with inventory stock validation.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.cart.models import Cart, CartItem
from apps.catalog.models import ProductVariant
from apps.inventory.models import InventoryItem
from apps.inventory.services import InsufficientStockError


class CartService:
    """
    Service layer providing core operations on shopping carts:
    adding items, updating quantities, removing items, and clearing carts.
    All quantity operations validate against live available stock.
    """

    @classmethod
    def add_item(
        cls,
        *,
        cart: Cart,
        variant: ProductVariant,
        quantity: int = 1,
    ) -> CartItem:
        """
        Adds a specified quantity of a product variant SKU to the cart.
        If the SKU is already in the cart, increments the existing quantity.
        Validates that the resulting total quantity does not exceed available stock.

        Args:
            cart: Target Cart instance.
            variant: ProductVariant instance being added.
            quantity: Quantity to add (must be >= 1).

        Returns:
            CartItem: The created or updated CartItem.

        Raises:
            ValidationError: If quantity is less than 1 or variant is inactive.
            InsufficientStockError: If requested quantity exceeds currently available stock.
        """
        if quantity <= 0:
            raise ValidationError("Quantity to add must be at least 1.")

        if not variant.is_active:
            raise ValidationError(f"SKU '{variant.sku}' is inactive and cannot be added to cart.")

        with transaction.atomic():
            cart_item = CartItem.objects.filter(cart=cart, variant=variant).first()
            current_cart_qty = cart_item.quantity if cart_item else 0
            desired_total_qty = current_cart_qty + quantity

            # Check live inventory stock
            inventory = InventoryItem.objects.filter(variant=variant).first()
            available_stock = inventory.available_quantity if inventory is not None else 0

            if desired_total_qty > available_stock:
                raise InsufficientStockError(
                    f"Insufficient stock for SKU '{variant.sku}'. "
                    f"Available: {available_stock}, Requested total: {desired_total_qty} "
                    f"(already in cart: {current_cart_qty})."
                )

            if cart_item is not None:
                cart_item.quantity = desired_total_qty
                cart_item.save(update_fields=["quantity", "updated_at"])
            else:
                cart_item = CartItem.objects.create(
                    cart=cart,
                    variant=variant,
                    quantity=quantity,
                )

            return cart_item

    @classmethod
    def update_quantity(
        cls,
        *,
        cart: Cart,
        item_id: int,
        quantity: int,
    ) -> CartItem:
        """
        Updates the quantity for an existing item in the cart.
        Validates the new quantity against live available stock.

        Args:
            cart: Target Cart instance.
            item_id: ID of the CartItem to update.
            quantity: New quantity value (must be >= 1).

        Returns:
            CartItem: The updated CartItem.

        Raises:
            ValidationError: If quantity is less than 1 or item is not found in cart.
            InsufficientStockError: If new quantity exceeds available stock.
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be at least 1.")

        with transaction.atomic():
            cart_item = (
                CartItem.objects.filter(cart=cart, id=item_id)
                .select_related("variant")
                .first()
            )
            if cart_item is None:
                raise ValidationError(f"CartItem with ID {item_id} does not exist in this cart.")

            variant = cart_item.variant
            inventory = InventoryItem.objects.filter(variant=variant).first()
            available_stock = inventory.available_quantity if inventory is not None else 0

            if quantity > available_stock:
                raise InsufficientStockError(
                    f"Insufficient stock for SKU '{variant.sku}'. "
                    f"Available: {available_stock}, Requested: {quantity}."
                )

            cart_item.quantity = quantity
            cart_item.save(update_fields=["quantity", "updated_at"])
            return cart_item

    @classmethod
    def remove_item(
        cls,
        *,
        cart: Cart,
        item_id: int,
    ) -> bool:
        """
        Removes an item from the cart.

        Args:
            cart: Target Cart instance.
            item_id: ID of the CartItem to remove.

        Returns:
            bool: True if removed successfully.

        Raises:
            ValidationError: If item is not found in cart.
        """
        cart_item = CartItem.objects.filter(cart=cart, id=item_id).first()
        if cart_item is None:
            raise ValidationError(f"CartItem with ID {item_id} does not exist in this cart.")

        cart_item.delete()
        return True

    @classmethod
    def clear_cart(
        cls,
        *,
        cart: Cart,
    ) -> int:
        """
        Removes all items from the given cart.

        Args:
            cart: Target Cart instance.

        Returns:
            int: Number of items deleted.
        """
        deleted_count, _ = cart.items.all().delete()
        return deleted_count
