"""
Unit tests for cart domain models, selectors, and CartService.
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.cart.models import Cart, CartItem
from apps.cart.selectors import (
    get_cart_by_id,
    get_cart_item,
    get_or_create_user_cart,
    get_user_cart,
)
from apps.cart.services import CartService
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import InventoryItem
from apps.inventory.services import InsufficientStockError

User = get_user_model()


@pytest.fixture
def sample_cart_data(db):
    user = User.objects.create_user(username="cart_tester", password="password123")
    other_user = User.objects.create_user(username="other_tester", password="password123")

    cat = Category.objects.create(name="Apparel", slug="apparel")
    product = Product.objects.create(
        category=cat,
        title="Classic Hoodie",
        slug="classic-hoodie",
        base_price=Decimal("50.00"),
    )
    variant1 = ProductVariant.objects.create(
        product=product,
        sku="HOODIE-BLK-M",
        variant_name="Black / M",
        price_override=None,
    )
    variant2 = ProductVariant.objects.create(
        product=product,
        sku="HOODIE-BLK-L",
        variant_name="Black / L",
        price_override=Decimal("55.00"),
    )
    inactive_variant = ProductVariant.objects.create(
        product=product,
        sku="HOODIE-DISCONTINUED",
        variant_name="Discontinued",
        is_active=False,
    )

    # Setup Inventory
    InventoryItem.objects.create(variant=variant1, quantity=10, reserved_quantity=2)  # Available: 8
    InventoryItem.objects.create(variant=variant2, quantity=3, reserved_quantity=0)   # Available: 3
    InventoryItem.objects.create(variant=inactive_variant, quantity=5, reserved_quantity=0)

    cart = Cart.objects.create(user=user)

    return {
        "user": user,
        "other_user": other_user,
        "cat": cat,
        "product": product,
        "variant1": variant1,
        "variant2": variant2,
        "inactive_variant": inactive_variant,
        "cart": cart,
    }


@pytest.mark.django_db
class TestCartModel:
    def test_create_cart_authenticated_user(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        assert cart.id is not None
        assert cart.user == sample_cart_data["user"]
        assert "cart_tester" in str(cart)

    def test_create_cart_guest_user(self):
        guest_cart = Cart.objects.create(user=None)
        assert guest_cart.id is not None
        assert guest_cart.user is None
        assert "Guest" in str(guest_cart)

    def test_cart_total_items_and_total_price_empty(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        assert cart.total_items == 0
        assert cart.total_price == Decimal("0.00")
        assert cart.is_empty is True

    def test_cart_total_items_and_total_price_with_items(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v1 = sample_cart_data["variant1"]  # price 50.00
        v2 = sample_cart_data["variant2"]  # price 55.00

        CartItem.objects.create(cart=cart, variant=v1, quantity=2)  # 2 * 50 = 100
        CartItem.objects.create(cart=cart, variant=v2, quantity=3)  # 3 * 55 = 165

        assert cart.total_items == 5
        assert cart.total_price == Decimal("265.00")
        assert cart.is_empty is False


@pytest.mark.django_db
class TestCartItemModel:
    def test_create_cart_item(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v1 = sample_cart_data["variant1"]
        item = CartItem.objects.create(cart=cart, variant=v1, quantity=2)

        assert item.id is not None
        assert item.unit_price == Decimal("50.00")
        assert item.subtotal == Decimal("100.00")
        assert "HOODIE-BLK-M" in str(item)

    def test_unique_cart_variant_constraint(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v1 = sample_cart_data["variant1"]
        CartItem.objects.create(cart=cart, variant=v1, quantity=1)

        with pytest.raises(IntegrityError):
            CartItem.objects.create(cart=cart, variant=v1, quantity=2)

    def test_positive_quantity_check_constraint(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v1 = sample_cart_data["variant1"]

        with pytest.raises(IntegrityError):
            CartItem.objects.create(cart=cart, variant=v1, quantity=0)


@pytest.mark.django_db
class TestCartSelectors:
    def test_get_or_create_user_cart_creates_new(self, sample_cart_data):
        other_user = sample_cart_data["other_user"]
        cart, created = get_or_create_user_cart(user=other_user)
        assert created is True
        assert cart.user == other_user

    def test_get_or_create_user_cart_returns_existing(self, sample_cart_data):
        user = sample_cart_data["user"]
        existing_cart = sample_cart_data["cart"]
        cart, created = get_or_create_user_cart(user=user)
        assert created is False
        assert cart.id == existing_cart.id

    def test_get_user_cart_returns_none_if_no_cart(self, sample_cart_data):
        other_user = sample_cart_data["other_user"]
        assert get_user_cart(user=other_user) is None

    def test_get_cart_by_id(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        fetched = get_cart_by_id(cart_id=cart.id)
        assert fetched is not None
        assert fetched.id == cart.id

    def test_get_cart_item(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v1 = sample_cart_data["variant1"]
        created_item = CartItem.objects.create(cart=cart, variant=v1, quantity=2)

        item = get_cart_item(cart=cart, item_id=created_item.id)
        assert item is not None
        assert item.id == created_item.id


@pytest.mark.django_db
class TestCartService:
    def test_add_item_new_variant_success(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v1 = sample_cart_data["variant1"]  # Available: 8

        item = CartService.add_item(cart=cart, variant=v1, quantity=3)
        assert item.id is not None
        assert item.quantity == 3
        assert item.variant == v1

    def test_add_item_existing_variant_increments_quantity(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v1 = sample_cart_data["variant1"]  # Available: 8

        CartService.add_item(cart=cart, variant=v1, quantity=2)
        updated_item = CartService.add_item(cart=cart, variant=v1, quantity=3)

        assert updated_item.quantity == 5
        assert CartItem.objects.filter(cart=cart, variant=v1).count() == 1

    def test_add_item_insufficient_stock_raises_error(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v2 = sample_cart_data["variant2"]  # Available: 3

        with pytest.raises(InsufficientStockError) as exc_info:
            CartService.add_item(cart=cart, variant=v2, quantity=4)

        assert "Insufficient stock for SKU 'HOODIE-BLK-L'" in str(exc_info.value)

    def test_add_item_cumulative_quantity_exceeds_stock_raises_error(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v2 = sample_cart_data["variant2"]  # Available: 3

        CartService.add_item(cart=cart, variant=v2, quantity=2)

        # Trying to add 2 more when only 3 total exist
        with pytest.raises(InsufficientStockError):
            CartService.add_item(cart=cart, variant=v2, quantity=2)

    def test_add_item_invalid_quantity_raises_error(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v1 = sample_cart_data["variant1"]

        with pytest.raises(ValidationError):
            CartService.add_item(cart=cart, variant=v1, quantity=0)

    def test_add_item_inactive_variant_raises_error(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        inactive = sample_cart_data["inactive_variant"]

        with pytest.raises(ValidationError) as exc_info:
            CartService.add_item(cart=cart, variant=inactive, quantity=1)
        assert "is inactive" in str(exc_info.value)

    def test_update_quantity_success(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v1 = sample_cart_data["variant1"]  # Available: 8

        item = CartService.add_item(cart=cart, variant=v1, quantity=2)
        updated_item = CartService.update_quantity(cart=cart, item_id=item.id, quantity=6)

        assert updated_item.quantity == 6

    def test_update_quantity_insufficient_stock_raises_error(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v1 = sample_cart_data["variant1"]  # Available: 8

        item = CartService.add_item(cart=cart, variant=v1, quantity=2)

        with pytest.raises(InsufficientStockError):
            CartService.update_quantity(cart=cart, item_id=item.id, quantity=12)

    def test_update_quantity_zero_or_negative_raises_error(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v1 = sample_cart_data["variant1"]

        item = CartService.add_item(cart=cart, variant=v1, quantity=2)

        with pytest.raises(ValidationError):
            CartService.update_quantity(cart=cart, item_id=item.id, quantity=0)

    def test_update_quantity_non_existent_item_raises_error(self, sample_cart_data):
        cart = sample_cart_data["cart"]

        with pytest.raises(ValidationError):
            CartService.update_quantity(cart=cart, item_id=9999, quantity=2)

    def test_remove_item_success(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v1 = sample_cart_data["variant1"]

        item = CartService.add_item(cart=cart, variant=v1, quantity=2)
        assert CartItem.objects.filter(cart=cart).count() == 1

        result = CartService.remove_item(cart=cart, item_id=item.id)
        assert result is True
        assert CartItem.objects.filter(cart=cart).count() == 0

    def test_remove_item_foreign_cart_raises_error(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        other_user = sample_cart_data["other_user"]
        other_cart = Cart.objects.create(user=other_user)
        v1 = sample_cart_data["variant1"]

        item_in_cart = CartService.add_item(cart=cart, variant=v1, quantity=1)

        with pytest.raises(ValidationError):
            CartService.remove_item(cart=other_cart, item_id=item_in_cart.id)

    def test_clear_cart_success(self, sample_cart_data):
        cart = sample_cart_data["cart"]
        v1 = sample_cart_data["variant1"]
        v2 = sample_cart_data["variant2"]

        CartService.add_item(cart=cart, variant=v1, quantity=2)
        CartService.add_item(cart=cart, variant=v2, quantity=1)
        assert cart.items.count() == 2

        deleted_count = CartService.clear_cart(cart=cart)
        assert deleted_count == 2
        assert cart.items.count() == 0
