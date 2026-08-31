"""
Unit tests for order domain models, selectors, and CheckoutService.
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import InventoryItem, InventoryTransaction
from apps.inventory.services import InsufficientStockError
from apps.orders.models import Order, OrderItem
from apps.orders.selectors import get_order_by_id, list_user_orders
from apps.orders.services import CheckoutService

User = get_user_model()


@pytest.fixture
def checkout_setup(db):
    user = User.objects.create_user(username="checkout_user", password="password123")
    other_user = User.objects.create_user(username="other_user", password="password123")

    cat = Category.objects.create(name="Footwear", slug="footwear")
    product1 = Product.objects.create(
        category=cat,
        title="Pro Runner 1",
        slug="pro-runner-1",
        base_price=Decimal("100.00"),
    )
    product2 = Product.objects.create(
        category=cat,
        title="Pro Runner 2",
        slug="pro-runner-2",
        base_price=Decimal("150.00"),
    )

    var1 = ProductVariant.objects.create(
        product=product1,
        sku="RUN1-BLK-42",
        variant_name="Black 42",
        price_override=Decimal("110.00"),
    )
    var2 = ProductVariant.objects.create(
        product=product2,
        sku="RUN2-WHT-43",
        variant_name="White 43",
        price_override=None,  # 150.00
    )
    inactive_var = ProductVariant.objects.create(
        product=product1,
        sku="RUN1-DISCONTINUED",
        variant_name="Discontinued",
        is_active=False,
    )

    inv1 = InventoryItem.objects.create(variant=var1, quantity=10, reserved_quantity=0)  # Available: 10
    inv2 = InventoryItem.objects.create(variant=var2, quantity=2, reserved_quantity=0)  # Available: 2
    InventoryItem.objects.create(variant=inactive_var, quantity=5, reserved_quantity=0)

    cart = Cart.objects.create(user=user)

    return {
        "user": user,
        "other_user": other_user,
        "product1": product1,
        "product2": product2,
        "var1": var1,
        "var2": var2,
        "inactive_var": inactive_var,
        "inv1": inv1,
        "inv2": inv2,
        "cart": cart,
    }


@pytest.mark.django_db
class TestOrderModel:
    def test_create_order(self, checkout_setup):
        user = checkout_setup["user"]
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("200.00"),
            shipping_address="123 Main St",
        )
        assert order.id is not None
        assert order.status == Order.OrderStatus.PENDING
        assert order.total_amount == Decimal("200.00")
        assert order.shipping_address == "123 Main St"
        assert str(order).startswith(f"Order {order.id}")

    def test_order_total_items(self, checkout_setup):
        user = checkout_setup["user"]
        var1 = checkout_setup["var1"]
        var2 = checkout_setup["var2"]

        order = Order.objects.create(user=user, total_amount=Decimal("260.00"))
        OrderItem.objects.create(
            order=order,
            variant=var1,
            sku=var1.sku,
            product_title=var1.product.title,
            unit_price=Decimal("110.00"),
            quantity=2,
            subtotal=Decimal("220.00"),
        )
        OrderItem.objects.create(
            order=order,
            variant=var2,
            sku=var2.sku,
            product_title=var2.product.title,
            unit_price=Decimal("150.00"),
            quantity=1,
            subtotal=Decimal("150.00"),
        )

        assert order.total_items == 3


@pytest.mark.django_db
class TestOrderItemModel:
    def test_create_order_item_with_snapshots(self, checkout_setup):
        user = checkout_setup["user"]
        var1 = checkout_setup["var1"]
        order = Order.objects.create(user=user, total_amount=Decimal("110.00"))

        item = OrderItem.objects.create(
            order=order,
            variant=var1,
            sku="SNAPSHOT-SKU",
            product_title="Snapshot Title",
            unit_price=Decimal("110.00"),
            quantity=1,
            subtotal=Decimal("110.00"),
        )
        assert item.id is not None
        assert item.sku == "SNAPSHOT-SKU"
        assert item.product_title == "Snapshot Title"
        assert "SNAPSHOT-SKU" in str(item)


@pytest.mark.django_db
class TestOrderSelectors:
    def test_list_user_orders(self, checkout_setup):
        user = checkout_setup["user"]
        other_user = checkout_setup["other_user"]

        Order.objects.create(user=user, total_amount=Decimal("100.00"))
        Order.objects.create(user=user, total_amount=Decimal("200.00"))
        Order.objects.create(user=other_user, total_amount=Decimal("300.00"))

        user_orders = list_user_orders(user=user)
        assert user_orders.count() == 2

    def test_get_order_by_id_and_isolation(self, checkout_setup):
        user = checkout_setup["user"]
        other_user = checkout_setup["other_user"]

        order = Order.objects.create(user=user, total_amount=Decimal("100.00"))

        # Lookup by owner
        found = get_order_by_id(order_id=order.id, user=user)
        assert found is not None
        assert found.id == order.id

        # Lookup by non-owner
        forbidden = get_order_by_id(order_id=order.id, user=other_user)
        assert forbidden is None


@pytest.mark.django_db
class TestCheckoutService:
    def test_successful_checkout_single_item(self, checkout_setup):
        user = checkout_setup["user"]
        cart = checkout_setup["cart"]
        var1 = checkout_setup["var1"]  # Initial stock: 10, Price: 110.00
        inv1 = checkout_setup["inv1"]

        CartItem.objects.create(cart=cart, variant=var1, quantity=3)

        order = CheckoutService.process_checkout(
            cart=cart,
            user=user,
            shipping_address="456 Elm Street",
        )

        # 1. Order assertions
        assert order.id is not None
        assert order.user == user
        assert order.status == Order.OrderStatus.PENDING
        assert order.total_amount == Decimal("330.00")
        assert order.shipping_address == "456 Elm Street"

        # 2. OrderItem assertions
        items = order.items.all()
        assert items.count() == 1
        order_item = items.first()
        assert order_item.sku == "RUN1-BLK-42"
        assert order_item.product_title == "Pro Runner 1"
        assert order_item.unit_price == Decimal("110.00")
        assert order_item.quantity == 3
        assert order_item.subtotal == Decimal("330.00")

        # 3. Inventory decrement
        inv1.refresh_from_db()
        assert inv1.quantity == 7  # 10 - 3

        # 4. Stock Audit Ledger assertions
        ledger = InventoryTransaction.objects.filter(inventory_item=inv1).first()
        assert ledger is not None
        assert ledger.transaction_type == InventoryTransaction.TransactionType.PURCHASE_DEDUCTION
        assert ledger.quantity_delta == -3
        assert ledger.balance_after == 7
        assert ledger.reference_id == f"ORDER-{order.id}"

        # 5. Cart cleared
        assert cart.items.count() == 0

    def test_successful_checkout_multiple_items_and_ordering(self, checkout_setup):
        user = checkout_setup["user"]
        cart = checkout_setup["cart"]
        var1 = checkout_setup["var1"]  # Price: 110.00, Stock: 10
        var2 = checkout_setup["var2"]  # Price: 150.00, Stock: 2
        inv1 = checkout_setup["inv1"]
        inv2 = checkout_setup["inv2"]

        CartItem.objects.create(cart=cart, variant=var1, quantity=2)  # 220.00
        CartItem.objects.create(cart=cart, variant=var2, quantity=1)  # 150.00

        order = CheckoutService.process_checkout(
            cart=cart,
            user=user,
            shipping_address="789 Pine Ave",
        )

        assert order.total_amount == Decimal("370.00")
        assert order.items.count() == 2

        inv1.refresh_from_db()
        inv2.refresh_from_db()
        assert inv1.quantity == 8
        assert inv2.quantity == 1

        assert InventoryTransaction.objects.filter(reference_id=f"ORDER-{order.id}").count() == 2
        assert cart.items.count() == 0

    def test_checkout_empty_cart_raises_error(self, checkout_setup):
        user = checkout_setup["user"]
        cart = checkout_setup["cart"]

        with pytest.raises(ValidationError) as exc_info:
            CheckoutService.process_checkout(cart=cart, user=user)

        assert "empty cart" in str(exc_info.value).lower()

    def test_checkout_insufficient_stock_raises_error_and_rolls_back(self, checkout_setup):
        user = checkout_setup["user"]
        cart = checkout_setup["cart"]
        var1 = checkout_setup["var1"]  # Stock: 10
        var2 = checkout_setup["var2"]  # Stock: 2
        inv1 = checkout_setup["inv1"]
        inv2 = checkout_setup["inv2"]

        CartItem.objects.create(cart=cart, variant=var1, quantity=2)
        CartItem.objects.create(cart=cart, variant=var2, quantity=5)  # Exceeds available stock (2)

        with pytest.raises(InsufficientStockError) as exc_info:
            CheckoutService.process_checkout(cart=cart, user=user)

        assert "Insufficient stock for SKU 'RUN2-WHT-43'" in str(exc_info.value)

        # Verify rollback: stock remains untouched
        inv1.refresh_from_db()
        inv2.refresh_from_db()
        assert inv1.quantity == 10
        assert inv2.quantity == 2

        # No order created
        assert Order.objects.filter(user=user).count() == 0
        assert InventoryTransaction.objects.count() == 0

        # Cart items still intact
        assert cart.items.count() == 2

    def test_checkout_inactive_variant_raises_error(self, checkout_setup):
        user = checkout_setup["user"]
        cart = checkout_setup["cart"]
        inactive_var = checkout_setup["inactive_var"]

        CartItem.objects.create(cart=cart, variant=inactive_var, quantity=1)

        with pytest.raises(ValidationError) as exc_info:
            CheckoutService.process_checkout(cart=cart, user=user)

        assert "is inactive" in str(exc_info.value)
