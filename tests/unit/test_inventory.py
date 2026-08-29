"""
Unit tests for inventory domain models, constraints, audit ledger, and StockService.
"""

from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import InventoryItem, InventoryTransaction
from apps.inventory.selectors import get_inventory_for_variant, list_inventory_transactions
from apps.inventory.services import InsufficientStockError, StockService


@pytest.fixture
def product_variant(db):
    cat = Category.objects.create(name="Shoes", slug="shoes")
    product = Product.objects.create(
        category=cat,
        title="Running Sneaker",
        slug="running-sneaker",
        base_price=Decimal("120.00"),
    )
    return ProductVariant.objects.create(
        product=product,
        sku="RUN-SNK-42",
        variant_name="EU 42",
    )


@pytest.mark.django_db
class TestInventoryItemModel:
    def test_create_inventory_item(self, product_variant):
        inventory = InventoryItem.objects.create(
            variant=product_variant,
            quantity=15,
            reserved_quantity=3,
        )
        assert inventory.id is not None
        assert inventory.available_quantity == 12
        assert inventory.is_in_stock is True
        assert "RUN-SNK-42" in str(inventory)

    def test_available_quantity_zero_when_reserved_exceeds_or_equals(self, product_variant):
        inventory = InventoryItem.objects.create(
            variant=product_variant,
            quantity=5,
            reserved_quantity=5,
        )
        assert inventory.available_quantity == 0
        assert inventory.is_in_stock is False

    def test_one_to_one_variant_constraint(self, product_variant):
        InventoryItem.objects.create(variant=product_variant, quantity=5)
        with pytest.raises(IntegrityError):
            InventoryItem.objects.create(variant=product_variant, quantity=10)


@pytest.mark.django_db
class TestInventoryTransactionModel:
    def test_create_ledger_entry(self, product_variant):
        inventory = InventoryItem.objects.create(variant=product_variant, quantity=20)
        txn = InventoryTransaction.objects.create(
            inventory_item=inventory,
            transaction_type=InventoryTransaction.TransactionType.RESTOCK,
            quantity_delta=20,
            balance_after=20,
            reference_id="PO-1001",
            notes="Initial stock arrival",
        )
        assert txn.id is not None
        assert txn.transaction_type == InventoryTransaction.TransactionType.RESTOCK
        assert "RESTOCK (+20)" in str(txn)


@pytest.mark.django_db
class TestStockService:
    def test_adjust_stock_positive(self, product_variant):
        txn = StockService.adjust_stock(
            variant=product_variant,
            delta=10,
            transaction_type=InventoryTransaction.TransactionType.RESTOCK,
            reference_id="PO-001",
            notes="Received 10 units",
        )
        assert txn.quantity_delta == 10
        assert txn.balance_after == 10

        inventory = InventoryItem.objects.get(variant=product_variant)
        assert inventory.quantity == 10
        assert inventory.available_quantity == 10

    def test_adjust_stock_negative(self, product_variant):
        # Initial stock: 10
        StockService.restock(variant=product_variant, quantity=10)

        # Deduct 4
        txn = StockService.adjust_stock(
            variant=product_variant,
            delta=-4,
            transaction_type=InventoryTransaction.TransactionType.PURCHASE_DEDUCTION,
            reference_id="ORD-101",
            notes="Purchased 4 units",
        )
        assert txn.quantity_delta == -4
        assert txn.balance_after == 6

        inventory = InventoryItem.objects.get(variant=product_variant)
        assert inventory.quantity == 6

    def test_adjust_stock_insufficient_raises_error(self, product_variant):
        StockService.restock(variant=product_variant, quantity=5)

        with pytest.raises(InsufficientStockError) as exc_info:
            StockService.adjust_stock(
                variant=product_variant,
                delta=-6,
                transaction_type=InventoryTransaction.TransactionType.PURCHASE_DEDUCTION,
            )

        assert "Insufficient stock" in str(exc_info.value)

        # Inventory unchanged and no new ledger entry created
        inventory = InventoryItem.objects.get(variant=product_variant)
        assert inventory.quantity == 5
        assert InventoryTransaction.objects.filter(inventory_item=inventory).count() == 1

    def test_restock_convenience_method(self, product_variant):
        txn = StockService.restock(variant=product_variant, quantity=25, reference_id="RESTOCK-99")
        assert txn.transaction_type == InventoryTransaction.TransactionType.RESTOCK
        assert txn.quantity_delta == 25
        assert txn.balance_after == 25

        with pytest.raises(ValidationError):
            StockService.restock(variant=product_variant, quantity=0)

    def test_deduct_stock_convenience_method(self, product_variant):
        StockService.restock(variant=product_variant, quantity=15)
        txn = StockService.deduct_stock(variant=product_variant, quantity=5, reference_id="ORD-55")
        assert txn.transaction_type == InventoryTransaction.TransactionType.PURCHASE_DEDUCTION
        assert txn.quantity_delta == -5
        assert txn.balance_after == 10

        with pytest.raises(ValidationError):
            StockService.deduct_stock(variant=product_variant, quantity=0)


@pytest.mark.django_db
class TestInventorySelectors:
    def test_get_inventory_for_variant(self, product_variant):
        assert get_inventory_for_variant(product_variant) is None
        inv = InventoryItem.objects.create(variant=product_variant, quantity=8)
        assert get_inventory_for_variant(product_variant) == inv

    def test_list_inventory_transactions(self, product_variant):
        StockService.restock(variant=product_variant, quantity=10, reference_id="PO-1")
        StockService.deduct_stock(variant=product_variant, quantity=2, reference_id="ORD-1")

        all_txns = list(list_inventory_transactions(variant_id=product_variant.id))
        assert len(all_txns) == 2

        restock_txns = list(
            list_inventory_transactions(
                variant_id=product_variant.id,
                transaction_type=InventoryTransaction.TransactionType.RESTOCK,
            )
        )
        assert len(restock_txns) == 1
        assert restock_txns[0].quantity_delta == 10
