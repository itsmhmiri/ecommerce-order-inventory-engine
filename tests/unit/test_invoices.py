"""
Unit tests for InvoiceService: Synchronous ReportLab PDF invoice generation.
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import Category, Product, ProductVariant
from apps.orders.models import Order, OrderItem
from apps.orders.services import InvoiceService
from apps.payments.models import PaymentTransaction

User = get_user_model()


@pytest.fixture
def invoice_order_setup(db):
    user = User.objects.create_user(
        username="invoice_tester",
        email="tester@example.com",
        password="password123",
    )
    category = Category.objects.create(name="Audio", slug="audio")
    product1 = Product.objects.create(
        category=category,
        title="Studio Monitor",
        slug="studio-monitor",
        base_price=Decimal("250.00"),
    )
    product2 = Product.objects.create(
        category=category,
        title="Audio Interface",
        slug="audio-interface",
        base_price=Decimal("150.00"),
    )

    variant1 = ProductVariant.objects.create(
        product=product1,
        sku="MON-8IN-BLK",
        variant_name="8-inch Pair",
        price_override=Decimal("280.00"),
    )
    variant2 = ProductVariant.objects.create(
        product=product2,
        sku="IF-USB-2CH",
        variant_name="2-Channel USB",
        price_override=None,
    )

    order = Order.objects.create(
        user=user,
        status=Order.OrderStatus.PENDING,
        total_amount=Decimal("710.00"),
        shipping_address="742 Evergreen Terrace, Springfield, OR",
    )

    OrderItem.objects.create(
        order=order,
        variant=variant1,
        sku=variant1.sku,
        product_title=product1.title,
        unit_price=Decimal("280.00"),
        quantity=2,
        subtotal=Decimal("560.00"),
    )
    OrderItem.objects.create(
        order=order,
        variant=variant2,
        sku=variant2.sku,
        product_title=product2.title,
        unit_price=Decimal("150.00"),
        quantity=1,
        subtotal=Decimal("150.00"),
    )

    return {
        "user": user,
        "order": order,
        "variant1": variant1,
        "variant2": variant2,
    }


@pytest.mark.django_db
class TestInvoiceService:
    def test_generate_pdf_returns_valid_pdf_stream(self, invoice_order_setup):
        order = invoice_order_setup["order"]

        pdf_buffer = InvoiceService.generate_pdf(order)

        assert pdf_buffer is not None
        pdf_bytes = pdf_buffer.getvalue()

        # PDF files must start with %PDF-
        assert pdf_bytes.startswith(b"%PDF-")
        # Ensure non-trivial payload generated
        assert len(pdf_bytes) > 1000

    def test_generate_pdf_paid_order_with_payment_transaction(self, invoice_order_setup):
        order = invoice_order_setup["order"]
        order.status = Order.OrderStatus.PAID
        order.save(update_fields=["status"])

        PaymentTransaction.objects.create(
            order=order,
            amount=order.total_amount,
            status=PaymentTransaction.PaymentStatus.SUCCESS,
            simulated_gateway_ref="SIM-PAY-SUCCESS999",
        )

        pdf_buffer = InvoiceService.generate_pdf(order)
        pdf_bytes = pdf_buffer.getvalue()

        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 1000

    def test_generate_pdf_failed_order_with_payment_transaction(self, invoice_order_setup):
        order = invoice_order_setup["order"]
        order.status = Order.OrderStatus.FAILED
        order.save(update_fields=["status"])

        PaymentTransaction.objects.create(
            order=order,
            amount=order.total_amount,
            status=PaymentTransaction.PaymentStatus.FAILED,
            simulated_gateway_ref="SIM-PAY-FAILED001",
            error_message="Card expired",
        )

        pdf_buffer = InvoiceService.generate_pdf(order)
        pdf_bytes = pdf_buffer.getvalue()

        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 1000

    def test_generate_pdf_with_blank_shipping_address(self, invoice_order_setup):
        order = invoice_order_setup["order"]
        order.shipping_address = ""
        order.save(update_fields=["shipping_address"])

        pdf_buffer = InvoiceService.generate_pdf(order)
        pdf_bytes = pdf_buffer.getvalue()

        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 1000
