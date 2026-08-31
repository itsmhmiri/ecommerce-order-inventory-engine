"""
Payment simulation service layer: Deterministic simulated payment state machine and compensation restocking.
"""

import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.inventory.models import InventoryItem, InventoryTransaction
from apps.orders.models import Order
from apps.payments.models import PaymentTransaction


class PaymentSimulationService:
    """
    Service responsible for simulating payment processing.
    Transitions orders from PENDING -> PAID (on success) or PENDING -> FAILED (on failure).
    When payment fails, triggers an atomic compensation transaction to restock inventory.
    """

    @classmethod
    def process_payment(
        cls,
        *,
        order: Order,
        simulate_success: bool = True,
        failure_reason: str = "Card declined by issuer.",
        gateway_ref: str | None = None,
    ) -> PaymentTransaction:
        """
        Executes a simulated payment transaction for an Order.

        Args:
            order: The Order instance to process payment for.
            simulate_success: If True, marks payment as SUCCESS and order as PAID.
                             If False, marks payment as FAILED and triggers compensation restock.
            failure_reason: Custom decline message when simulate_success=False.
            gateway_ref: Optional custom reference string (auto-generated if None).

        Returns:
            PaymentTransaction: The newly created payment transaction record.

        Raises:
            ValidationError: If the order is not in PENDING status or has already been paid/processed.
        """
        if gateway_ref is None:
            gateway_ref = f"SIM-PAY-{uuid.uuid4().hex[:12].upper()}"

        with transaction.atomic():
            # 1. Lock the order row to prevent concurrent double-payments
            locked_order = (
                Order.objects.select_for_update().prefetch_related("items", "items__variant").get(id=order.id)
            )

            if locked_order.status == Order.OrderStatus.PAID:
                raise ValidationError("Order has already been paid.")

            if locked_order.status != Order.OrderStatus.PENDING:
                raise ValidationError(f"Cannot process payment for order in '{locked_order.status}' status.")

            if hasattr(locked_order, "payment_transaction") and locked_order.payment_transaction is not None:
                raise ValidationError("A payment transaction already exists for this order.")

            if simulate_success:
                # 2. SUCCESS PATH: Transition order to PAID
                locked_order.status = Order.OrderStatus.PAID
                locked_order.save(update_fields=["status", "updated_at"])

                payment = PaymentTransaction.objects.create(
                    order=locked_order,
                    amount=locked_order.total_amount,
                    status=PaymentTransaction.PaymentStatus.SUCCESS,
                    simulated_gateway_ref=gateway_ref,
                    error_message="",
                )
                return payment

            # 3. FAILURE PATH: Transition order to FAILED and execute compensation restock
            locked_order.status = Order.OrderStatus.FAILED
            locked_order.save(update_fields=["status", "updated_at"])

            payment = PaymentTransaction.objects.create(
                order=locked_order,
                amount=locked_order.total_amount,
                status=PaymentTransaction.PaymentStatus.FAILED,
                simulated_gateway_ref=gateway_ref,
                error_message=failure_reason or "Payment failed.",
            )

            # Compensation transaction: Restock inventory for all items in the failed order
            order_items = list(locked_order.items.select_related("variant").all())
            variant_ids = sorted([item.variant_id for item in order_items])

            locked_inventory = {
                inv.variant_id: inv
                for inv in InventoryItem.objects.select_for_update()
                .filter(variant_id__in=variant_ids)
                .order_by("variant_id")
            }

            for item in order_items:
                inventory = locked_inventory.get(item.variant_id)
                if inventory is not None:
                    inventory.quantity += item.quantity
                    inventory.save(update_fields=["quantity", "updated_at"])

                    InventoryTransaction.objects.create(
                        inventory_item=inventory,
                        transaction_type=InventoryTransaction.TransactionType.RESTOCK,
                        quantity_delta=item.quantity,
                        balance_after=inventory.quantity,
                        reference_id=f"RESTOCK-ORDER-{locked_order.id}",
                        notes=f"Compensation restock for failed payment on order {locked_order.id}",
                    )

            return payment
