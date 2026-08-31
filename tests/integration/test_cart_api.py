"""
Integration tests for Cart REST API endpoints.
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import InventoryItem

User = get_user_model()


@pytest.fixture
def cart_api_setup(db):
    user_a = User.objects.create_user(username="alice", email="alice@example.com", password="password123")
    user_b = User.objects.create_user(username="bob", email="bob@example.com", password="password123")

    client_a = APIClient()
    client_a.force_authenticate(user=user_a)

    client_b = APIClient()
    client_b.force_authenticate(user=user_b)

    cat = Category.objects.create(name="Shoes", slug="shoes")
    prod = Product.objects.create(
        category=cat,
        title="Running Shoes",
        slug="running-shoes",
        base_price=Decimal("120.00"),
    )
    var_a = ProductVariant.objects.create(
        product=prod,
        sku="SHOE-RED-42",
        variant_name="Red / 42",
        price_override=Decimal("125.00"),
    )
    var_b = ProductVariant.objects.create(
        product=prod,
        sku="SHOE-BLU-42",
        variant_name="Blue / 42",
        price_override=None,  # 120.00
    )
    # Inventory
    InventoryItem.objects.create(variant=var_a, quantity=5, reserved_quantity=0)  # Available: 5
    InventoryItem.objects.create(variant=var_b, quantity=2, reserved_quantity=0)  # Available: 2

    return {
        "user_a": user_a,
        "user_b": user_b,
        "client_a": client_a,
        "client_b": client_b,
        "var_a": var_a,
        "var_b": var_b,
    }


@pytest.mark.django_db
class TestCartAPIAuthentication:
    def test_anonymous_access_forbidden(self, api_client):
        assert api_client.get("/api/v1/cart/").status_code == status.HTTP_401_UNAUTHORIZED
        assert api_client.delete("/api/v1/cart/").status_code == status.HTTP_401_UNAUTHORIZED
        assert api_client.post("/api/v1/cart/items/", {"variant_id": 1, "quantity": 1}).status_code == status.HTTP_401_UNAUTHORIZED
        assert api_client.patch("/api/v1/cart/items/1/", {"quantity": 2}).status_code == status.HTTP_401_UNAUTHORIZED
        assert api_client.delete("/api/v1/cart/items/1/").status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestCartAPIOperations:
    def test_get_cart_creates_empty_cart_on_demand(self, cart_api_setup):
        client = cart_api_setup["client_a"]
        user_a = cart_api_setup["user_a"]

        response = client.get("/api/v1/cart/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["user_id"] == user_a.id
        assert response.data["items"] == []
        assert response.data["total_items"] == 0
        assert response.data["total_price"] == "0.00"

    def test_add_item_to_cart_success(self, cart_api_setup):
        client = cart_api_setup["client_a"]
        var_a = cart_api_setup["var_a"]

        response = client.post(
            "/api/v1/cart/items/",
            {"variant_id": var_a.id, "quantity": 2},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["quantity"] == 2
        assert response.data["unit_price"] == "125.00"
        assert response.data["subtotal"] == "250.00"
        assert response.data["variant"]["sku"] == "SHOE-RED-42"
        assert response.data["variant"]["available_stock"] == 5

        # Check cart detail
        cart_response = client.get("/api/v1/cart/")
        assert cart_response.status_code == status.HTTP_200_OK
        assert cart_response.data["total_items"] == 2
        assert cart_response.data["total_price"] == "250.00"
        assert len(cart_response.data["items"]) == 1

    def test_add_item_insufficient_stock_fails(self, cart_api_setup):
        client = cart_api_setup["client_a"]
        var_b = cart_api_setup["var_b"]  # Available: 2

        response = client.post(
            "/api/v1/cart/items/",
            {"variant_id": var_b.id, "quantity": 3},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Insufficient stock" in str(response.data)

    def test_add_item_non_existent_variant_fails(self, cart_api_setup):
        client = cart_api_setup["client_a"]
        response = client.post(
            "/api/v1/cart/items/",
            {"variant_id": 99999, "quantity": 1},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_add_same_item_increments_quantity(self, cart_api_setup):
        client = cart_api_setup["client_a"]
        var_a = cart_api_setup["var_a"]  # Available: 5

        # Add 2
        client.post("/api/v1/cart/items/", {"variant_id": var_a.id, "quantity": 2}, format="json")
        # Add 2 more
        res = client.post("/api/v1/cart/items/", {"variant_id": var_a.id, "quantity": 2}, format="json")

        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["quantity"] == 4

        # Cart total check
        cart_res = client.get("/api/v1/cart/")
        assert cart_res.data["total_items"] == 4
        assert len(cart_res.data["items"]) == 1

    def test_patch_item_quantity(self, cart_api_setup):
        client = cart_api_setup["client_a"]
        var_a = cart_api_setup["var_a"]  # Available: 5

        add_res = client.post("/api/v1/cart/items/", {"variant_id": var_a.id, "quantity": 1}, format="json")
        item_id = add_res.data["id"]

        patch_res = client.patch(f"/api/v1/cart/items/{item_id}/", {"quantity": 4}, format="json")
        assert patch_res.status_code == status.HTTP_200_OK
        assert patch_res.data["quantity"] == 4
        assert patch_res.data["subtotal"] == "500.00"

    def test_patch_item_quantity_exceeding_stock_fails(self, cart_api_setup):
        client = cart_api_setup["client_a"]
        var_a = cart_api_setup["var_a"]  # Available: 5

        add_res = client.post("/api/v1/cart/items/", {"variant_id": var_a.id, "quantity": 1}, format="json")
        item_id = add_res.data["id"]

        patch_res = client.patch(f"/api/v1/cart/items/{item_id}/", {"quantity": 10}, format="json")
        assert patch_res.status_code == status.HTTP_400_BAD_REQUEST
        assert "Insufficient stock" in str(patch_res.data)

    def test_delete_cart_item(self, cart_api_setup):
        client = cart_api_setup["client_a"]
        var_a = cart_api_setup["var_a"]

        add_res = client.post("/api/v1/cart/items/", {"variant_id": var_a.id, "quantity": 1}, format="json")
        item_id = add_res.data["id"]

        delete_res = client.delete(f"/api/v1/cart/items/{item_id}/")
        assert delete_res.status_code == status.HTTP_204_NO_CONTENT

        cart_res = client.get("/api/v1/cart/")
        assert cart_res.data["total_items"] == 0
        assert cart_res.data["items"] == []

    def test_clear_cart_endpoint(self, cart_api_setup):
        client = cart_api_setup["client_a"]
        var_a = cart_api_setup["var_a"]
        var_b = cart_api_setup["var_b"]

        client.post("/api/v1/cart/items/", {"variant_id": var_a.id, "quantity": 1}, format="json")
        client.post("/api/v1/cart/items/", {"variant_id": var_b.id, "quantity": 1}, format="json")

        clear_res = client.delete("/api/v1/cart/")
        assert clear_res.status_code == status.HTTP_204_NO_CONTENT

        cart_res = client.get("/api/v1/cart/")
        assert cart_res.data["total_items"] == 0
        assert cart_res.data["items"] == []


@pytest.mark.django_db
class TestCartAPIIsolation:
    def test_user_cannot_access_or_modify_other_user_cart_items(self, cart_api_setup):
        client_a = cart_api_setup["client_a"]
        client_b = cart_api_setup["client_b"]
        var_a = cart_api_setup["var_a"]

        # Alice adds an item to her cart
        add_res = client_a.post("/api/v1/cart/items/", {"variant_id": var_a.id, "quantity": 2}, format="json")
        alice_item_id = add_res.data["id"]

        # Bob's cart should be empty
        bob_cart = client_b.get("/api/v1/cart/")
        assert bob_cart.data["total_items"] == 0
        assert bob_cart.data["items"] == []

        # Bob tries to patch Alice's cart item
        patch_res = client_b.patch(f"/api/v1/cart/items/{alice_item_id}/", {"quantity": 1}, format="json")
        assert patch_res.status_code == status.HTTP_404_NOT_FOUND

        # Bob tries to delete Alice's cart item
        delete_res = client_b.delete(f"/api/v1/cart/items/{alice_item_id}/")
        assert delete_res.status_code == status.HTTP_404_NOT_FOUND

        # Alice's cart item is untouched
        alice_cart = client_a.get("/api/v1/cart/")
        assert alice_cart.data["total_items"] == 2
        assert len(alice_cart.data["items"]) == 1
