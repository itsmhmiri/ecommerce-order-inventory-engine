"""
Integration tests for database-backed Idempotency on checkout and payment endpoints.
"""

import uuid
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import InventoryItem
from apps.orders.models import Order
from apps.payments.models import PaymentTransaction

User = get_user_model()


@pytest.fixture
def idemp_api_setup(db):
    user = User.objects.create_user(username="idemp_shopper", email="shopper@idemp.com", password="password123")
    client = APIClient()
    client.force_authenticate(user=user)

    cat = Category.objects.create(name="Gadgets", slug="gadgets")
    prod = Product.objects.create(category=cat, title="Drone", slug="drone", base_price=Decimal("500.00"))
    variant = ProductVariant.objects.create(
        product=prod, sku="DRONE-001", variant_name="Standard", price_override=Decimal("500.00")
    )
    inv = InventoryItem.objects.create(variant=variant, quantity=10, reserved_quantity=0)

    cart = Cart.objects.create(user=user)

    return {
        "user": user,
        "client": client,
        "variant": variant,
        "inv": inv,
        "cart": cart,
    }


@pytest.mark.django_db
class TestCheckoutIdempotencyAPI:
    def test_checkout_replay_returns_identical_response_without_duplicate_order(self, idemp_api_setup):
        client = idemp_api_setup["client"]
        cart = idemp_api_setup["cart"]
        variant = idemp_api_setup["variant"]
        inv = idemp_api_setup["inv"]

        CartItem.objects.create(cart=cart, variant=variant, quantity=2)

        idempotency_key = f"idemp-checkout-{uuid.uuid4()}"
        payload = {"shipping_address": "456 Drone Blvd"}

        # First request
        res1 = client.post(
            "/api/v1/orders/checkout/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )
        assert res1.status_code == status.HTTP_201_CREATED
        order_id_1 = res1.data["id"]

        # Second request with SAME idempotency key and payload
        res2 = client.post(
            "/api/v1/orders/checkout/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )
        assert res2.status_code == status.HTTP_201_CREATED
        assert res2.data["id"] == order_id_1

        # Exactly 1 Order created in the system
        assert Order.objects.count() == 1

        # Inventory decremented only once (10 - 2 = 8)
        inv.refresh_from_db()
        assert inv.quantity == 8

    def test_checkout_payload_mismatch_returns_422(self, idemp_api_setup):
        client = idemp_api_setup["client"]
        cart = idemp_api_setup["cart"]
        variant = idemp_api_setup["variant"]

        CartItem.objects.create(cart=cart, variant=variant, quantity=1)
        idempotency_key = f"idemp-mismatch-{uuid.uuid4()}"

        res1 = client.post(
            "/api/v1/orders/checkout/",
            {"shipping_address": "Address A"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )
        assert res1.status_code == status.HTTP_201_CREATED

        # Second request with modified payload
        res2 = client.post(
            "/api/v1/orders/checkout/",
            {"shipping_address": "Address B"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )
        assert res2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.django_db
class TestPaymentIdempotencyAPI:
    def test_payment_replay_returns_identical_response_without_duplicate_transaction(self, idemp_api_setup):
        client = idemp_api_setup["client"]
        user = idemp_api_setup["user"]

        order = Order.objects.create(
            user=user,
            status=Order.OrderStatus.PENDING,
            total_amount=Decimal("500.00"),
        )

        idempotency_key = f"idemp-pay-{uuid.uuid4()}"
        payload = {"simulate_success": True}

        # First payment attempt
        res1 = client.post(
            f"/api/v1/orders/{order.id}/pay/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )
        assert res1.status_code == status.HTTP_200_OK
        payment_id = res1.data["id"]

        # Second payment attempt with same idempotency key
        res2 = client.post(
            f"/api/v1/orders/{order.id}/pay/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )
        assert res2.status_code == status.HTTP_200_OK
        assert res2.data["id"] == payment_id

        # Exactly 1 payment transaction exists
        assert PaymentTransaction.objects.count() == 1
