"""
Integration tests for catalog REST API endpoints.
"""

from decimal import Decimal
import pytest
from rest_framework import status
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import InventoryItem


@pytest.fixture
def catalog_data(db):
    cat_clothing = Category.objects.create(name="Clothing", slug="clothing")
    cat_accessories = Category.objects.create(name="Accessories", slug="accessories")

    # Product 1: T-Shirt with 2 variants
    p1 = Product.objects.create(
        category=cat_clothing,
        title="Oversized T-Shirt",
        slug="oversized-t-shirt",
        description="Premium heavy cotton",
        base_price=Decimal("45.00"),
    )
    v1 = ProductVariant.objects.create(product=p1, sku="TSHIRT-BLK-S", variant_name="Small / Black")
    v2 = ProductVariant.objects.create(
        product=p1,
        sku="TSHIRT-BLK-XL",
        variant_name="XL / Black",
        price_override=Decimal("49.00"),
    )
    InventoryItem.objects.create(variant=v1, quantity=10)
    InventoryItem.objects.create(variant=v2, quantity=0)

    # Product 2: Cap
    p2 = Product.objects.create(
        category=cat_accessories,
        title="Baseball Cap",
        slug="baseball-cap",
        base_price=Decimal("25.00"),
    )
    v3 = ProductVariant.objects.create(product=p2, sku="CAP-NVY", variant_name="Navy")
    InventoryItem.objects.create(variant=v3, quantity=5)

    return {
        "cat_clothing": cat_clothing,
        "cat_accessories": cat_accessories,
        "p1": p1,
        "p2": p2,
        "v1": v1,
        "v2": v2,
        "v3": v3,
    }


@pytest.mark.django_db
class TestCatalogAPI:
    def test_list_products_unauthenticated(self, api_client, catalog_data):
        url = "/api/v1/catalog/products/"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data
        assert response.data["count"] == 2

        # Verify first product payload structure
        first_product = response.data["results"][0]
        assert "title" in first_product
        assert "slug" in first_product
        assert "variants" in first_product
        assert len(first_product["variants"]) >= 1

    def test_list_products_filter_by_category(self, api_client, catalog_data):
        url = "/api/v1/catalog/products/?category=clothing"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["slug"] == "oversized-t-shirt"

    def test_retrieve_product_detail_by_slug(self, api_client, catalog_data):
        url = "/api/v1/catalog/products/oversized-t-shirt/"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["slug"] == "oversized-t-shirt"
        assert response.data["title"] == "Oversized T-Shirt"

        variants = response.data["variants"]
        assert len(variants) == 2

        # Variant 1: in stock
        var1 = next(v for v in variants if v["sku"] == "TSHIRT-BLK-S")
        assert var1["effective_price"] == "45.00"
        assert var1["stock_quantity"] == 10
        assert var1["is_in_stock"] is True

        # Variant 2: out of stock with price override
        var2 = next(v for v in variants if v["sku"] == "TSHIRT-BLK-XL")
        assert var2["effective_price"] == "49.00"
        assert var2["stock_quantity"] == 0
        assert var2["is_in_stock"] is False

    def test_retrieve_non_existent_product_returns_404(self, api_client):
        url = "/api/v1/catalog/products/unknown-product-slug/"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_categories(self, api_client, catalog_data):
        url = "/api/v1/catalog/categories/"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_retrieve_category_by_slug(self, api_client, catalog_data):
        url = "/api/v1/catalog/categories/clothing/"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["slug"] == "clothing"
        assert response.data["name"] == "Clothing"
