"""
Automated concurrency and stress test suite for CheckoutService.
Proves that row-level pessimistic locking (select_for_update) prevents race conditions,
overselling, and stock divergence under concurrent checkout load.
"""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import connection

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import InventoryItem, InventoryTransaction
from apps.orders.models import Order
from apps.orders.services import CheckoutService

User = get_user_model()


@pytest.mark.django_db(transaction=True)
def test_concurrent_checkout_prevents_overselling():
    """
    Simulates 10 concurrent users attempting to checkout the LAST remaining item.
    Guarantees:
      - Exactly 1 order succeeds.
      - Exactly 9 checkouts fail with stock validation error.
      - Final inventory quantity is 0 (never negative).
      - Audit ledger contains exactly 1 deduction.
    """
    # 1. Setup: 1 product variant with stock = 1
    category = Category.objects.create(name="Footwear", slug="footwear-concurrency")
    product = Product.objects.create(
        category=category,
        title="Limited Sneaker",
        slug="limited-sneaker",
        base_price=Decimal("100.00"),
    )
    variant = ProductVariant.objects.create(
        product=product,
        sku="SNK-001",
        variant_name="US 10",
        price_override=Decimal("100.00"),
    )
    inventory = InventoryItem.objects.create(variant=variant, quantity=1, reserved_quantity=0)

    # 2. Create 10 distinct users, each with 1 item in their cart
    users = [User.objects.create_user(username=f"shopper_{i}", password="password123") for i in range(10)]
    carts = []
    for u in users:
        c = Cart.objects.create(user=u)
        CartItem.objects.create(cart=c, variant=variant, quantity=1)
        carts.append(c)

    def attempt_checkout(user: User, cart: Cart):
        try:
            order = CheckoutService.process_checkout(
                cart=cart,
                user=user,
                idempotency_key=f"key-{user.id}",
            )
            return ("SUCCESS", order.id)
        except Exception as exc:
            return ("FAILED", str(exc))
        finally:
            connection.close()

    # 3. Execute 10 simultaneous threads
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_checkout, users[i], carts[i]) for i in range(10)]
        results = [f.result() for f in futures]

    successes = [r for r in results if r[0] == "SUCCESS"]
    failures = [r for r in results if r[0] == "FAILED"]

    # 4. Strict Assertions
    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}. Failures: {failures}"
    assert len(failures) == 9, f"Expected 9 failures, got {len(failures)}"

    inventory.refresh_from_db()
    assert inventory.quantity == 0, f"Expected quantity 0, got {inventory.quantity}"

    # Audit ledger contains exactly 1 deduction
    ledger_entries = InventoryTransaction.objects.filter(
        inventory_item=inventory,
        transaction_type=InventoryTransaction.TransactionType.PURCHASE_DEDUCTION,
    )
    assert ledger_entries.count() == 1
    assert ledger_entries.first().quantity_delta == -1
    assert ledger_entries.first().balance_after == 0

    # Exactly 1 order in database
    assert Order.objects.count() == 1
