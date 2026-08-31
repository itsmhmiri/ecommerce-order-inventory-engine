"""
Unit tests for catalog domain models and selectors.
"""

from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.catalog.models import Category, Product, ProductVariant
from apps.catalog.selectors import (
    get_category_by_slug,
    get_product_by_slug,
    list_active_categories,
    list_active_products,
)


@pytest.mark.django_db
class TestCategoryModel:
    def test_create_category(self):
        cat = Category.objects.create(name="Footwear", slug="footwear")
        assert cat.id is not None
        assert cat.name == "Footwear"
        assert cat.slug == "footwear"
        assert cat.is_active is True
        assert str(cat) == "Footwear"

    def test_unique_slug_constraint(self):
        Category.objects.create(name="Shoes", slug="shoes")
        with pytest.raises(IntegrityError):
            Category.objects.create(name="Other Shoes", slug="shoes")


@pytest.mark.django_db
class TestProductModel:
    def test_create_product(self):
        cat = Category.objects.create(name="Apparel", slug="apparel")
        product = Product.objects.create(
            category=cat,
            title="Classic T-Shirt",
            slug="classic-t-shirt",
            description="100% Cotton T-Shirt",
            base_price=Decimal("29.99"),
        )
        assert product.id is not None
        assert product.category == cat
        assert product.base_price == Decimal("29.99")
        assert str(product) == "Classic T-Shirt"

    def test_product_unique_slug(self):
        cat = Category.objects.create(name="Apparel", slug="apparel")
        Product.objects.create(category=cat, title="P1", slug="product-1", base_price=Decimal("10.00"))
        with pytest.raises(IntegrityError):
            Product.objects.create(category=cat, title="P2", slug="product-1", base_price=Decimal("20.00"))


@pytest.mark.django_db
class TestProductVariantModel:
    def test_effective_price_fallback_to_base_price(self):
        cat = Category.objects.create(name="Apparel", slug="apparel")
        product = Product.objects.create(
            category=cat,
            title="Hoodie",
            slug="hoodie",
            base_price=Decimal("59.99"),
        )
        variant = ProductVariant.objects.create(
            product=product,
            sku="HOODIE-M",
            variant_name="Size M",
            price_override=None,
        )
        assert variant.effective_price == Decimal("59.99")
        assert str(variant) == "Hoodie - Size M (HOODIE-M)"

    def test_effective_price_with_override(self):
        cat = Category.objects.create(name="Apparel", slug="apparel")
        product = Product.objects.create(
            category=cat,
            title="Hoodie",
            slug="hoodie",
            base_price=Decimal("59.99"),
        )
        variant = ProductVariant.objects.create(
            product=product,
            sku="HOODIE-XXL",
            variant_name="Size XXL",
            price_override=Decimal("69.99"),
        )
        assert variant.effective_price == Decimal("69.99")

    def test_unique_sku_constraint(self):
        cat = Category.objects.create(name="Apparel", slug="apparel")
        product = Product.objects.create(
            category=cat,
            title="Cap",
            slug="cap",
            base_price=Decimal("15.00"),
        )
        ProductVariant.objects.create(product=product, sku="CAP-BLK", variant_name="Black")
        with pytest.raises(IntegrityError):
            ProductVariant.objects.create(product=product, sku="CAP-BLK", variant_name="Duplicate")


@pytest.mark.django_db
class TestCatalogSelectors:
    def test_list_active_categories(self):
        Category.objects.create(name="Active Cat", slug="active-cat", is_active=True)
        Category.objects.create(name="Inactive Cat", slug="inactive-cat", is_active=False)

        categories = list(list_active_categories())
        assert len(categories) == 1
        assert categories[0].slug == "active-cat"

    def test_get_category_by_slug(self):
        Category.objects.create(name="Gadgets", slug="gadgets", is_active=True)
        cat = get_category_by_slug("gadgets")
        assert cat is not None
        assert cat.name == "Gadgets"
        assert get_category_by_slug("non-existent") is None

    def test_list_active_products_and_filter(self):
        cat1 = Category.objects.create(name="Cat 1", slug="cat-1")
        cat2 = Category.objects.create(name="Cat 2", slug="cat-2")

        Product.objects.create(category=cat1, title="P1", slug="p1", base_price=Decimal("10.00"), is_active=True)
        Product.objects.create(category=cat2, title="P2", slug="p2", base_price=Decimal("20.00"), is_active=True)
        Product.objects.create(category=cat1, title="Inactive", slug="p-inactive", base_price=Decimal("30.00"), is_active=False)

        active = list(list_active_products())
        assert len(active) == 2

        cat1_products = list(list_active_products(category_slug="cat-1"))
        assert len(cat1_products) == 1
        assert cat1_products[0].slug == "p1"

    def test_get_product_by_slug(self):
        cat = Category.objects.create(name="Electronics", slug="electronics")
        Product.objects.create(category=cat, title="Laptop", slug="laptop", base_price=Decimal("999.00"), is_active=True)

        product = get_product_by_slug("laptop")
        assert product is not None
        assert product.title == "Laptop"
        assert get_product_by_slug("non-existent") is None
