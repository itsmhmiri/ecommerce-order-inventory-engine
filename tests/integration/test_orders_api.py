"""
Integration tests for Orders REST API endpoints.
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import InventoryItem

User = get_user_model()


@pytest.fixture
def orders_api_setup(db):
    user_a = User.objects.create_user(username="alice", email="alice@example.com", password="password123")
    user_b = User.objects.create_user(username="bob", email="bob@example.com", password="password123")

    client_a = APIClient()
    client_a.force_authenticate(user=user_a)

    client_b = APIClient()
    client_b.force_authenticate(user=user_b)

    cat = Category.objects.create(name="Electronics", slug="electronics")
    prod = Product.objects.create(
        category=cat,
        title="Wireless Headphones",
        slug="wireless-headphones",
        base_price=Decimal("150.00"),
    )
    var1 = ProductVariant.objects.create(
        product=prod,
        sku="HEADPHONE-BLK",
        variant_name="Matte Black",
        price_override=Decimal("160.00"),
    )
    var2 = ProductVariant.objects.create(
        product=prod,
        sku="HEADPHONE-SLV",
        variant_name="Silver",
        price_override=None,  # 150.00
    )

    InventoryItem.objects.create(variant=var1, quantity=10, reserved_quantity=0)  # Available: 10
    InventoryItem.objects.create(variant=var2, quantity=1, reserved_quantity=0)  # Available: 1

    cart_a = Cart.objects.create(user=user_a)
    cart_b = Cart.objects.create(user=user_b)

    return {
        "user_a": user_a,
        "user_b": user_b,
        "client_a": client_a,
        "client_b": client_b,
        "var1": var1,
        "var2": var2,
        "cart_a": cart_a,
        "cart_b": cart_b,
    }


@pytest.mark.django_db
class TestOrdersAPIAuthentication:
    def test_anonymous_access_forbidden(self, api_client):
        assert api_client.post("/api/v1/orders/checkout/", {}).status_code == status.HTTP_401_UNAUTHORIZED
        assert api_client.get("/api/v1/orders/").status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestOrdersAPICheckout:
    def test_checkout_empty_cart_returns_400(self, orders_api_setup):
        client = orders_api_setup["client_a"]
        response = client.post("/api/v1/orders/checkout/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cart is empty" in str(response.data)

    def test_checkout_success(self, orders_api_setup):
        client = orders_api_setup["client_a"]
        cart_a = orders_api_setup["cart_a"]
        var1 = orders_api_setup["var1"]  # 160.00

        CartItem.objects.create(cart=cart_a, variant=var1, quantity=2)

        payload = {"shipping_address": "123 Technology Way"}
        response = client.post(
            "/api/v1/orders/checkout/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="test-idemp-123",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "PENDING"
        assert response.data["total_amount"] == "320.00"
        assert response.data["shipping_address"] == "123 Technology Way"
        assert response.data["total_items"] == 2
        assert len(response.data["items"]) == 1

        first_item = response.data["items"][0]
        assert first_item["sku"] == "HEADPHONE-BLK"
        assert first_item["unit_price"] == "160.00"
        assert first_item["quantity"] == 2
        assert first_item["subtotal"] == "320.00"

        # Check cart is now empty
        cart_response = client.get("/api/v1/cart/")
        assert cart_response.data["total_items"] == 0

    def test_checkout_insufficient_stock_returns_400(self, orders_api_setup):
        client = orders_api_setup["client_a"]
        cart_a = orders_api_setup["cart_a"]
        var2 = orders_api_setup["var2"]  # Available: 1

        CartItem.objects.create(cart=cart_a, variant=var2, quantity=5)

        response = client.post("/api/v1/orders/checkout/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Insufficient stock" in str(response.data)


@pytest.mark.django_db
class TestOrdersAPIListAndRetrieve:
    def test_list_user_orders(self, orders_api_setup):
        client = orders_api_setup["client_a"]
        cart_a = orders_api_setup["cart_a"]
        var1 = orders_api_setup["var1"]

        # Place 2 orders for Alice
        CartItem.objects.create(cart=cart_a, variant=var1, quantity=1)
        client.post("/api/v1/orders/checkout/", format="json")

        CartItem.objects.create(cart=cart_a, variant=var1, quantity=1)
        client.post("/api/v1/orders/checkout/", format="json")

        response = client.get("/api/v1/orders/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_retrieve_order_details_and_isolation(self, orders_api_setup):
        client_a = orders_api_setup["client_a"]
        client_b = orders_api_setup["client_b"]
        cart_a = orders_api_setup["cart_a"]
        var1 = orders_api_setup["var1"]

        CartItem.objects.create(cart=cart_a, variant=var1, quantity=1)
        checkout_res = client_a.post("/api/v1/orders/checkout/", format="json")
        order_id = checkout_res.data["id"]

        # Alice retrieves her own order
        alice_res = client_a.get(f"/api/v1/orders/{order_id}/")
        assert alice_res.status_code == status.HTTP_200_OK
        assert alice_res.data["id"] == order_id

        # Bob tries to access Alice's order
        bob_res = client_b.get(f"/api/v1/orders/{order_id}/")
        assert bob_res.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_non_existent_order_returns_404(self, orders_api_setup):
        import uuid

        client_a = orders_api_setup["client_a"]
        res = client_a.get(f"/api/v1/orders/{uuid.uuid4()}/")
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_order_viewset_swagger_fake_view(self):
        from apps.orders.views import OrderReadOnlyViewSet

        view = OrderReadOnlyViewSet()
        view.swagger_fake_view = True
        assert view.get_queryset().count() == 0
