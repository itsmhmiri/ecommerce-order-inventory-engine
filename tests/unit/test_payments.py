"""
Unit tests for Payment domain model, selectors, and PaymentSimulationService.
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import InventoryItem, InventoryTransaction
from apps.orders.models import Order, OrderItem
from apps.payments.models import PaymentTransaction
from apps.payments.selectors import get_payment_by_id, get_payment_for_order, list_user_payments
from apps.payments.services import PaymentSimulationService

User = get_user_model()


@pytest.fixture
def payment_setup(db):
    user = User.objects.create_user(username="pay_user", password="password123")
    other_user = User.objects.create_user(username="other_pay_user", password="password123")

    cat = Category.objects.create(name="Shoes", slug="shoes")
    prod = Product.objects.create(category=cat, title="Sneaker", slug="sneaker", base_price=Decimal("100.00"))
    var1 = ProductVariant.objects.create(
        product=prod, sku="SNK-BLK", variant_name="Black", price_override=Decimal("120.00")
    )
    var2 = ProductVariant.objects.create(product=prod, sku="SNK-WHT", variant_name="White", price_override=None)

    inv1 = InventoryItem.objects.create(variant=var1, quantity=5, reserved_quantity=0)
    inv2 = InventoryItem.objects.create(variant=var2, quantity=3, reserved_quantity=0)

    order = Order.objects.create(
        user=user,
        status=Order.OrderStatus.PENDING,
        total_amount=Decimal("340.00"),
        shipping_address="123 Payment Way",
    )
    OrderItem.objects.create(
        order=order,
        variant=var1,
        sku=var1.sku,
        product_title=prod.title,
        unit_price=Decimal("120.00"),
        quantity=2,
        subtotal=Decimal("240.00"),
    )
    OrderItem.objects.create(
        order=order,
        variant=var2,
        sku=var2.sku,
        product_title=prod.title,
        unit_price=Decimal("100.00"),
        quantity=1,
        subtotal=Decimal("100.00"),
    )

    return {
        "user": user,
        "other_user": other_user,
        "order": order,
        "inv1": inv1,
        "inv2": inv2,
        "var1": var1,
        "var2": var2,
    }


@pytest.mark.django_db
class TestPaymentTransactionModel:
    def test_create_payment_transaction(self, payment_setup):
        order = payment_setup["order"]
        payment = PaymentTransaction.objects.create(
            order=order,
            amount=Decimal("340.00"),
            status=PaymentTransaction.PaymentStatus.SUCCESS,
            simulated_gateway_ref="SIM-PAY-TEST12345",
        )
        assert payment.id is not None
        assert payment.status == PaymentTransaction.PaymentStatus.SUCCESS
        assert payment.amount == Decimal("340.00")
        assert "SIM-PAY-TEST12345" in str(payment)


@pytest.mark.django_db
class TestPaymentSimulationService:
    def test_simulate_payment_success(self, payment_setup):
        order = payment_setup["order"]
        inv1 = payment_setup["inv1"]
        inv2 = payment_setup["inv2"]

        payment = PaymentSimulationService.process_payment(
            order=order,
            simulate_success=True,
            gateway_ref="GW-SUCCESS-001",
        )

        assert payment.id is not None
        assert payment.status == PaymentTransaction.PaymentStatus.SUCCESS
        assert payment.simulated_gateway_ref == "GW-SUCCESS-001"
        assert payment.error_message == ""

        order.refresh_from_db()
        assert order.status == Order.OrderStatus.PAID

        # Stock should remain decremented (unchanged by payment success)
        inv1.refresh_from_db()
        inv2.refresh_from_db()
        assert inv1.quantity == 5
        assert inv2.quantity == 3
        assert (
            InventoryTransaction.objects.filter(transaction_type=InventoryTransaction.TransactionType.RESTOCK).count()
            == 0
        )

    def test_simulate_payment_failure_triggers_compensation_restock(self, payment_setup):
        order = payment_setup["order"]
        inv1 = payment_setup["inv1"]
        inv2 = payment_setup["inv2"]

        payment = PaymentSimulationService.process_payment(
            order=order,
            simulate_success=False,
            failure_reason="Insufficient funds",
            gateway_ref="GW-FAIL-001",
        )

        assert payment.id is not None
        assert payment.status == PaymentTransaction.PaymentStatus.FAILED
        assert payment.simulated_gateway_ref == "GW-FAIL-001"
        assert payment.error_message == "Insufficient funds"

        order.refresh_from_db()
        assert order.status == Order.OrderStatus.FAILED

        # Compensation restocking should have occurred
        inv1.refresh_from_db()
        inv2.refresh_from_db()
        assert inv1.quantity == 7  # 5 + 2
        assert inv2.quantity == 4  # 3 + 1

        # Audit ledger entries should be created for each restocked SKU
        restock_txs = InventoryTransaction.objects.filter(
            transaction_type=InventoryTransaction.TransactionType.RESTOCK,
            reference_id=f"RESTOCK-ORDER-{order.id}",
        )
        assert restock_txs.count() == 2

    def test_payment_on_already_paid_order_raises_error(self, payment_setup):
        order = payment_setup["order"]
        order.status = Order.OrderStatus.PAID
        order.save()

        with pytest.raises(ValidationError) as exc_info:
            PaymentSimulationService.process_payment(order=order, simulate_success=True)

        assert "already been paid" in str(exc_info.value)

    def test_payment_on_cancelled_order_raises_error(self, payment_setup):
        order = payment_setup["order"]
        order.status = Order.OrderStatus.CANCELLED
        order.save()

        with pytest.raises(ValidationError) as exc_info:
            PaymentSimulationService.process_payment(order=order, simulate_success=True)

        assert "CANCELLED" in str(exc_info.value)

    def test_duplicate_payment_transaction_raises_error(self, payment_setup):
        order = payment_setup["order"]
        PaymentSimulationService.process_payment(order=order, simulate_success=True)

        # Reset status back to PENDING artificially to test duplicate transaction guard
        order.status = Order.OrderStatus.PENDING
        order.save()

        with pytest.raises(ValidationError) as exc_info:
            PaymentSimulationService.process_payment(order=order, simulate_success=True)

        assert "already exists" in str(exc_info.value)


@pytest.mark.django_db
class TestPaymentSelectors:
    def test_list_and_get_payment_selectors(self, payment_setup):
        user = payment_setup["user"]
        other_user = payment_setup["other_user"]
        order = payment_setup["order"]

        payment = PaymentSimulationService.process_payment(order=order, simulate_success=True)

        # List user payments
        user_payments = list_user_payments(user=user)
        assert user_payments.count() == 1
        assert list_user_payments(user=other_user).count() == 0

        # Get by id
        assert get_payment_by_id(payment_id=payment.id, user=user) is not None
        assert get_payment_by_id(payment_id=payment.id, user=other_user) is None

        # Get for order
        assert get_payment_for_order(order_id=order.id, user=user) is not None
        assert get_payment_for_order(order_id=order.id, user=other_user) is None
