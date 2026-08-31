"""
Order and Checkout service layer: High-concurrency atomic checkout with row-level pessimistic locking.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.cart.models import Cart
from apps.inventory.models import InventoryItem, InventoryTransaction
from apps.inventory.services import InsufficientStockError
from apps.orders.models import Order, OrderItem

User = get_user_model()


class CheckoutService:
    """
    Service responsible for executing atomic, deadlock-free checkouts.
    Acquires row-level pessimistic locks (SELECT FOR UPDATE) on inventory rows
    in deterministic SKU order, validates stock, decrements quantities,
    creates immutable audit ledger records, creates order line items with historical snapshots,
    and clears the customer's cart.
    """

    @classmethod
    def process_checkout(
        cls,
        *,
        cart: Cart,
        user: User,
        shipping_address: str = "",
        idempotency_key: str = "",
    ) -> Order:
        """
        Executes an atomic checkout transaction for the user's cart.

        Args:
            cart: Cart containing items to checkout.
            user: Authenticated user placing the order.
            shipping_address: Optional delivery address.
            idempotency_key: Optional idempotency key reference.

        Returns:
            Order: The newly created Order instance with status PENDING.

        Raises:
            ValidationError: If the cart is empty or variant is inactive.
            InsufficientStockError: If any SKU lacks sufficient available quantity.
        """
        cart_items = list(cart.items.select_related("variant", "variant__product").all())
        if not cart_items:
            raise ValidationError("Cannot checkout with an empty cart.")

        # 1. Deterministic sorting of variant IDs to prevent database deadlocks
        variant_ids = sorted([item.variant_id for item in cart_items])

        with transaction.atomic():
            # 2. Acquire pessimistic row-level locks in deterministic order
            locked_inventory = {
                inv.variant_id: inv
                for inv in InventoryItem.objects.select_for_update()
                .filter(variant_id__in=variant_ids)
                .order_by("variant_id")
            }

            # 3. Validate stock availability for all items under lock
            for item in cart_items:
                if not item.variant.is_active:
                    raise ValidationError(
                        f"SKU '{item.variant.sku}' is inactive and cannot be purchased."
                    )

                inventory = locked_inventory.get(item.variant_id)
                available_stock = inventory.available_quantity if inventory is not None else 0

                if inventory is None or available_stock < item.quantity:
                    raise InsufficientStockError(
                        f"Insufficient stock for SKU '{item.variant.sku}'. "
                        f"Available: {available_stock}, Requested: {item.quantity}."
                    )

            # 4. Decrement inventory, compute financial amounts, and prepare line items
            order_total = Decimal("0.00")
            order_items_data = []

            for item in cart_items:
                inventory = locked_inventory[item.variant_id]
                inventory.quantity -= item.quantity
                inventory.save(update_fields=["quantity", "updated_at"])

                unit_price = item.variant.effective_price
                subtotal = unit_price * item.quantity
                order_total += subtotal

                order_items_data.append({
                    "variant": item.variant,
                    "inventory": inventory,
                    "sku": item.variant.sku,
                    "product_title": item.variant.product.title,
                    "unit_price": unit_price,
                    "quantity": item.quantity,
                    "subtotal": subtotal,
                })

            # 5. Create Order record
            order = Order.objects.create(
                user=user,
                status=Order.OrderStatus.PENDING,
                total_amount=order_total,
                shipping_address=shipping_address,
            )

            # 6. Create OrderItem historical snapshots and log InventoryTransactions
            for item_data in order_items_data:
                OrderItem.objects.create(
                    order=order,
                    variant=item_data["variant"],
                    sku=item_data["sku"],
                    product_title=item_data["product_title"],
                    unit_price=item_data["unit_price"],
                    quantity=item_data["quantity"],
                    subtotal=item_data["subtotal"],
                )

                # Record stock deduction in immutable audit ledger
                InventoryTransaction.objects.create(
                    inventory_item=item_data["inventory"],
                    transaction_type=InventoryTransaction.TransactionType.PURCHASE_DEDUCTION,
                    quantity_delta=-item_data["quantity"],
                    balance_after=item_data["inventory"].quantity,
                    reference_id=f"ORDER-{order.id}",
                    notes=f"Checkout purchase deduction for order {order.id}",
                )

            # 7. Clear cart items
            cart.items.all().delete()

            return order
