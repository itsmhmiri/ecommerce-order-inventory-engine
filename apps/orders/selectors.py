"""
Order selectors: Read-only database queries and retrieval for Order and OrderItem entities.
"""

from uuid import UUID

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from apps.orders.models import Order

User = get_user_model()


def list_user_orders(*, user: User) -> QuerySet[Order]:
    """
    Retrieves all orders placed by the specified user, prefetching related items, variants, and payments.
    """
    return (
        Order.objects.filter(user=user)
        .select_related("payment_transaction")
        .prefetch_related(
            "items",
            "items__variant",
            "items__variant__product",
        )
        .order_by("-created_at")
    )


def get_order_by_id(*, order_id: UUID, user: User | None = None) -> Order | None:
    """
    Retrieves a specific order by UUID, optionally restricting the lookup to a specific user.
    """
    qs = Order.objects.filter(id=order_id)
    if user is not None:
        qs = qs.filter(user=user)

    return (
        qs.select_related("user", "payment_transaction")
        .prefetch_related(
            "items",
            "items__variant",
            "items__variant__product",
        )
        .first()
    )
