"""
Payment selectors: Read-only database queries and retrieval for PaymentTransaction entities.
"""

from uuid import UUID

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from apps.payments.models import PaymentTransaction

User = get_user_model()


def list_user_payments(*, user: User) -> QuerySet[PaymentTransaction]:
    """
    Retrieves all payment transactions for orders placed by the specified user.
    """
    return PaymentTransaction.objects.filter(order__user=user).select_related("order").order_by("-created_at")


def get_payment_by_id(*, payment_id: UUID, user: User | None = None) -> PaymentTransaction | None:
    """
    Retrieves a specific payment transaction by UUID, optionally restricted to a specific user.
    """
    qs = PaymentTransaction.objects.filter(id=payment_id).select_related("order")
    if user is not None:
        qs = qs.filter(order__user=user)
    return qs.first()


def get_payment_for_order(*, order_id: UUID, user: User | None = None) -> PaymentTransaction | None:
    """
    Retrieves the payment transaction associated with a specific order ID.
    """
    qs = PaymentTransaction.objects.filter(order_id=order_id).select_related("order")
    if user is not None:
        qs = qs.filter(order__user=user)
    return qs.first()
