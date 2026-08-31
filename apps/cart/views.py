"""
Cart API views for retrieving, adding, updating, and removing items in shopping carts.
"""

from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, ValidationError as DRFValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.catalog.models import ProductVariant
from apps.inventory.services import InsufficientStockError
from apps.cart.selectors import get_or_create_user_cart, get_user_cart
from apps.cart.serializers import (
    AddCartItemInputSerializer,
    CartItemSerializer,
    CartSerializer,
    UpdateCartItemInputSerializer,
)
from apps.cart.services import CartService


class CartDetailView(APIView):
    """
    Retrieve or clear the authenticated user's current shopping cart.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Cart"],
        summary="Retrieve current user's cart",
        description="Fetch the active shopping cart for the authenticated user, including itemized lines and totals.",
        responses={200: CartSerializer},
    )
    def get(self, request: Request) -> Response:
        cart, _ = get_or_create_user_cart(user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Cart"],
        summary="Clear shopping cart",
        description="Remove all items from the current user's shopping cart.",
        responses={204: OpenApiResponse(description="Cart cleared successfully")},
    )
    def delete(self, request: Request) -> Response:
        cart = get_user_cart(user=request.user)
        if cart is not None:
            CartService.clear_cart(cart=cart)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemCreateView(APIView):
    """
    Add a product variant SKU to the authenticated user's shopping cart.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Cart"],
        summary="Add SKU variant to cart",
        description="Add a specified quantity of a product variant to the current user's cart with live stock validation.",
        request=AddCartItemInputSerializer,
        responses={
            201: CartItemSerializer,
            400: OpenApiResponse(description="Stock insufficient or invalid input"),
        },
    )
    def post(self, request: Request) -> Response:
        input_serializer = AddCartItemInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        variant_id = input_serializer.validated_data["variant_id"]
        quantity = input_serializer.validated_data.get("quantity", 1)

        variant = ProductVariant.objects.get(id=variant_id)
        cart, _ = get_or_create_user_cart(user=request.user)

        try:
            cart_item = CartService.add_item(
                cart=cart,
                variant=variant,
                quantity=quantity,
            )
        except (InsufficientStockError, DjangoValidationError) as exc:
            raise DRFValidationError(detail=getattr(exc, "messages", [str(exc)]))

        output_serializer = CartItemSerializer(cart_item)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    """
    Update or remove a specific line item in the authenticated user's cart.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Cart"],
        summary="Update item quantity in cart",
        description="Modify the quantity of a specific item in the authenticated user's cart.",
        request=UpdateCartItemInputSerializer,
        responses={
            200: CartItemSerializer,
            400: OpenApiResponse(description="Stock insufficient or invalid quantity"),
            404: OpenApiResponse(description="Cart item not found"),
        },
    )
    def patch(self, request: Request, item_id: int) -> Response:
        input_serializer = UpdateCartItemInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        quantity = input_serializer.validated_data["quantity"]
        cart, _ = get_or_create_user_cart(user=request.user)

        try:
            cart_item = CartService.update_quantity(
                cart=cart,
                item_id=item_id,
                quantity=quantity,
            )
        except (InsufficientStockError, DjangoValidationError) as exc:
            msg = getattr(exc, "messages", [str(exc)])
            # Check if this was a not found error
            if f"CartItem with ID {item_id} does not exist" in str(msg):
                raise NotFound(detail=f"CartItem with ID {item_id} does not exist in your cart.")
            raise DRFValidationError(detail=msg)

        output_serializer = CartItemSerializer(cart_item)
        return Response(output_serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Cart"],
        summary="Remove item from cart",
        description="Delete a specific line item from the authenticated user's cart.",
        responses={
            204: OpenApiResponse(description="Item removed successfully"),
            404: OpenApiResponse(description="Cart item not found"),
        },
    )
    def delete(self, request: Request, item_id: int) -> Response:
        cart, _ = get_or_create_user_cart(user=request.user)

        try:
            CartService.remove_item(cart=cart, item_id=item_id)
        except DjangoValidationError:
            raise NotFound(detail=f"CartItem with ID {item_id} does not exist in your cart.")

        return Response(status=status.HTTP_204_NO_CONTENT)
