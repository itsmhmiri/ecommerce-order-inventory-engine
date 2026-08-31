"""
Cart selectors: Read-only database queries and retrieval for Cart and CartItem entities.
"""

from uuid import UUID

from django.contrib.auth import get_user_model

from apps.cart.models import Cart, CartItem

User = get_user_model()


def get_user_cart(*, user: User) -> Cart | None:
    """
    Retrieves the most recent cart for the specified authenticated user,
    prefetching related variants, products, and inventory for efficient serialization.
    """
    return (
        Cart.objects.filter(user=user)
        .prefetch_related(
            "items__variant__product",
            "items__variant__product__category",
            "items__variant__inventory",
        )
        .first()
    )


def get_or_create_user_cart(*, user: User) -> tuple[Cart, bool]:
    """
    Retrieves the existing cart for the user or creates a new one.
    """
    cart = get_user_cart(user=user)
    if cart is not None:
        return cart, False
    created_cart = Cart.objects.create(user=user)
    return created_cart, True


def get_cart_by_id(*, cart_id: UUID) -> Cart | None:
    """
    Retrieves a specific cart by its UUID with prefetching.
    """
    return (
        Cart.objects.filter(id=cart_id)
        .prefetch_related(
            "items__variant__product",
            "items__variant__product__category",
            "items__variant__inventory",
        )
        .first()
    )


def get_cart_item(*, cart: Cart, item_id: int) -> CartItem | None:
    """
    Retrieves a specific CartItem belonging to the provided Cart.
    """
    return (
        CartItem.objects.filter(cart=cart, id=item_id)
        .select_related("variant", "variant__product", "variant__inventory")
        .first()
    )
