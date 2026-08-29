"""
Integration tests for inventory audit ledger API endpoints.
"""

from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.services import StockService

User = get_user_model()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="adminuser",
        email="admin@example.com",
        password="adminpassword123",
    )


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def inventory_ledger_data(db):
    cat = Category.objects.create(name="Shoes", slug="shoes")
    p = Product.objects.create(category=cat, title="Boot", slug="boot", base_price=Decimal("150.00"))
    v = ProductVariant.objects.create(product=p, sku="BOOT-40", variant_name="Size 40")

    StockService.restock(variant=v, quantity=20, reference_id="PO-001")
    StockService.deduct_stock(variant=v, quantity=2, reference_id="ORD-001")

    return {"variant": v}


@pytest.mark.django_db
class TestInventoryLedgerAPI:
    def test_ledger_anonymous_access_denied(self, api_client, inventory_ledger_data):
        url = "/api/v1/inventory/ledger/"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_ledger_regular_user_access_forbidden(self, authenticated_client, inventory_ledger_data):
        url = "/api/v1/inventory/ledger/"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_ledger_admin_access_allowed(self, admin_client, inventory_ledger_data):
        url = "/api/v1/inventory/ledger/"
        response = admin_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        results = response.data["results"]
        assert results[0]["variant_sku"] == "BOOT-40"
        assert results[0]["product_title"] == "Boot"

    def test_ledger_filter_by_transaction_type(self, admin_client, inventory_ledger_data):
        url = "/api/v1/inventory/ledger/?transaction_type=RESTOCK"
        response = admin_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["transaction_type"] == "RESTOCK"
