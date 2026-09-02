"""
Integration tests for the PDF Invoice download endpoint.
"""

import uuid
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductVariant
from apps.orders.models import Order, OrderItem

User = get_user_model()


@pytest.fixture
def invoice_api_setup(db):
    user_a = User.objects.create_user(
        username="alice_inv",
        email="alice@inv.com",
        password="password123",
    )
    user_b = User.objects.create_user(
        username="bob_inv",
        email="bob@inv.com",
        password="password123",
    )
    admin_user = User.objects.create_superuser(
        username="admin_inv",
        email="admin@inv.com",
        password="password123",
    )

    client_a = APIClient()
    client_a.force_authenticate(user=user_a)

    client_b = APIClient()
    client_b.force_authenticate(user=user_b)

    client_admin = APIClient()
    client_admin.force_authenticate(user=admin_user)

    cat = Category.objects.create(name="Keyboards", slug="keyboards")
    prod = Product.objects.create(
        category=cat,
        title="Mechanical Keyboard",
        slug="mechanical-keyboard",
        base_price=Decimal("120.00"),
    )
    variant = ProductVariant.objects.create(
        product=prod,
        sku="KB-MECH-RGB",
        variant_name="RGB Blue Switches",
        price_override=Decimal("130.00"),
    )

    order_a = Order.objects.create(
        user=user_a,
        status=Order.OrderStatus.PENDING,
        total_amount=Decimal("260.00"),
        shipping_address="100 Innovation Way, Silicon Valley, CA",
    )
    OrderItem.objects.create(
        order=order_a,
        variant=variant,
        sku=variant.sku,
        product_title=prod.title,
        unit_price=Decimal("130.00"),
        quantity=2,
        subtotal=Decimal("260.00"),
    )

    return {
        "user_a": user_a,
        "user_b": user_b,
        "admin_user": admin_user,
        "client_a": client_a,
        "client_b": client_b,
        "client_admin": client_admin,
        "order_a": order_a,
    }


@pytest.mark.django_db
class TestInvoiceAPI:
    def test_anonymous_access_forbidden(self, api_client):
        random_id = uuid.uuid4()
        response = api_client.get(f"/api/v1/orders/{random_id}/invoice/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_download_non_existent_order_invoice_returns_404(self, invoice_api_setup):
        client = invoice_api_setup["client_a"]
        random_id = uuid.uuid4()
        response = client.get(f"/api/v1/orders/{random_id}/invoice/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_tenant_isolation_other_user_cannot_download_invoice(self, invoice_api_setup):
        client_b = invoice_api_setup["client_b"]
        order_a = invoice_api_setup["order_a"]

        response = client_b.get(f"/api/v1/orders/{order_a.id}/invoice/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_owner_can_successfully_download_pdf_invoice(self, invoice_api_setup):
        client_a = invoice_api_setup["client_a"]
        order_a = invoice_api_setup["order_a"]

        response = client_a.get(f"/api/v1/orders/{order_a.id}/invoice/")

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["Content-Type"] == "application/pdf"
        assert f'filename="invoice_{order_a.id}.pdf"' in response.headers["Content-Disposition"]

        content = b"".join(response.streaming_content)
        assert content.startswith(b"%PDF-")
        assert len(content) > 1000

    def test_staff_admin_can_download_any_user_invoice(self, invoice_api_setup):
        client_admin = invoice_api_setup["client_admin"]
        order_a = invoice_api_setup["order_a"]

        response = client_admin.get(f"/api/v1/orders/{order_a.id}/invoice/")

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["Content-Type"] == "application/pdf"
        content = b"".join(response.streaming_content)
        assert content.startswith(b"%PDF-")
