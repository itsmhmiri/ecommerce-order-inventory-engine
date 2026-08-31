"""
Integration tests for Payment REST API endpoints.
"""

import uuid
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import InventoryItem
from apps.orders.models import Order, OrderItem

User = get_user_model()


@pytest.fixture
def payments_api_setup(db):
    user_a = User.objects.create_user(username="alice_pay", email="alice@pay.com", password="password123")
    user_b = User.objects.create_user(username="bob_pay", email="bob@pay.com", password="password123")

    client_a = APIClient()
    client_a.force_authenticate(user=user_a)

    client_b = APIClient()
    client_b.force_authenticate(user=user_b)

    cat = Category.objects.create(name="Wearables", slug="wearables")
    prod = Product.objects.create(category=cat, title="Smart Watch", slug="smart-watch", base_price=Decimal("200.00"))
    variant = ProductVariant.objects.create(
        product=prod, sku="WATCH-001", variant_name="Black", price_override=Decimal("200.00")
    )
    inv = InventoryItem.objects.create(variant=variant, quantity=10, reserved_quantity=0)

    # Create Order for Alice in PENDING status
    order_a = Order.objects.create(
        user=user_a,
        status=Order.OrderStatus.PENDING,
        total_amount=Decimal("400.00"),
        shipping_address="123 Alice St",
    )
    OrderItem.objects.create(
        order=order_a,
        variant=variant,
        sku=variant.sku,
        product_title=prod.title,
        unit_price=Decimal("200.00"),
        quantity=2,
        subtotal=Decimal("400.00"),
    )

    return {
        "user_a": user_a,
        "user_b": user_b,
        "client_a": client_a,
        "client_b": client_b,
        "order_a": order_a,
        "variant": variant,
        "inv": inv,
    }


@pytest.mark.django_db
class TestPaymentsAPIAuthentication:
    def test_anonymous_access_forbidden(self, api_client):
        random_id = uuid.uuid4()
        assert api_client.post(f"/api/v1/orders/{random_id}/pay/", {}).status_code == status.HTTP_401_UNAUTHORIZED
        assert api_client.get("/api/v1/payments/").status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestOrderPaymentAPI:
    def test_pay_non_existent_order_returns_404(self, payments_api_setup):
        client = payments_api_setup["client_a"]
        res = client.post(f"/api/v1/orders/{uuid.uuid4()}/pay/", {}, format="json")
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_pay_other_user_order_returns_404(self, payments_api_setup):
        client_b = payments_api_setup["client_b"]
        order_a = payments_api_setup["order_a"]

        res = client_b.post(f"/api/v1/orders/{order_a.id}/pay/", {}, format="json")
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_simulate_payment_success(self, payments_api_setup):
        client_a = payments_api_setup["client_a"]
        order_a = payments_api_setup["order_a"]

        payload = {"simulate_success": True}
        res = client_a.post(f"/api/v1/orders/{order_a.id}/pay/", payload, format="json")

        assert res.status_code == status.HTTP_200_OK
        assert res.data["status"] == "SUCCESS"
        assert res.data["amount"] == "400.00"
        assert res.data["order_id"] == str(order_a.id)

        order_a.refresh_from_db()
        assert order_a.status == Order.OrderStatus.PAID

    def test_simulate_payment_failure_and_compensation_restock(self, payments_api_setup):
        client_a = payments_api_setup["client_a"]
        order_a = payments_api_setup["order_a"]
        inv = payments_api_setup["inv"]

        payload = {"simulate_success": False, "failure_reason": "Insufficient balance"}
        res = client_a.post(f"/api/v1/orders/{order_a.id}/pay/", payload, format="json")

        assert res.status_code == status.HTTP_200_OK
        assert res.data["status"] == "FAILED"
        assert res.data["error_message"] == "Insufficient balance"

        order_a.refresh_from_db()
        assert order_a.status == Order.OrderStatus.FAILED

        # Stock is restocked
        inv.refresh_from_db()
        assert inv.quantity == 12  # 10 + 2

    def test_payment_on_already_paid_order_returns_400(self, payments_api_setup):
        client_a = payments_api_setup["client_a"]
        order_a = payments_api_setup["order_a"]

        # First payment succeeds
        client_a.post(f"/api/v1/orders/{order_a.id}/pay/", {"simulate_success": True}, format="json")

        # Second payment fails
        res = client_a.post(f"/api/v1/orders/{order_a.id}/pay/", {"simulate_success": True}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "already been paid" in str(res.data)


@pytest.mark.django_db
class TestPaymentReadOnlyViewSet:
    def test_list_user_payments_and_detail(self, payments_api_setup):
        client_a = payments_api_setup["client_a"]
        client_b = payments_api_setup["client_b"]
        order_a = payments_api_setup["order_a"]

        pay_res = client_a.post(f"/api/v1/orders/{order_a.id}/pay/", {"simulate_success": True}, format="json")
        payment_id = pay_res.data["id"]

        # List payments for Alice
        list_res = client_a.get("/api/v1/payments/")
        assert list_res.status_code == status.HTTP_200_OK
        assert list_res.data["count"] == 1

        # Retrieve payment detail for Alice
        detail_res = client_a.get(f"/api/v1/payments/{payment_id}/")
        assert detail_res.status_code == status.HTTP_200_OK
        assert detail_res.data["id"] == payment_id

        # Bob cannot see Alice's payment
        assert client_b.get("/api/v1/payments/").data["count"] == 0
        assert client_b.get(f"/api/v1/payments/{payment_id}/").status_code == status.HTTP_404_NOT_FOUND

    def test_payment_viewset_swagger_fake_view(self):
        from apps.payments.views import PaymentReadOnlyViewSet

        view = PaymentReadOnlyViewSet()
        view.swagger_fake_view = True
        assert view.get_queryset().count() == 0
