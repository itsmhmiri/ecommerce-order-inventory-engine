"""
Order API views: Atomic checkout and authenticated order history / detail retrieval.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart.selectors import get_user_cart
from apps.common.idempotency import idempotent_request
from apps.inventory.services import InsufficientStockError
from apps.orders.models import Order
from apps.orders.selectors import list_user_orders
from apps.orders.serializers import CheckoutInputSerializer, OrderSerializer
from apps.orders.services import CheckoutService


class CheckoutAPIView(APIView):
    """
    Executes an atomic checkout of the authenticated user's current shopping cart.
    Applies row-level pessimistic locking on inventory to guarantee zero overselling.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary="Atomic cart checkout",
        description=(
            "Atomically check out the authenticated user's shopping cart. "
            "Acquires pessimistic row-level locks on inventory items to prevent race conditions, "
            "creates order snapshots, records stock deductions in the audit ledger, and clears the cart."
        ),
        request=CheckoutInputSerializer,
        responses={
            201: OrderSerializer,
            400: OpenApiResponse(description="Cart is empty, stock is insufficient, or validation error"),
            409: OpenApiResponse(description="Request already in progress for this idempotency key"),
            422: OpenApiResponse(description="Idempotency key payload mismatch"),
        },
    )
    @idempotent_request
    def post(self, request: Request) -> Response:

        input_serializer = CheckoutInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        shipping_address = input_serializer.validated_data.get("shipping_address", "")
        idempotency_key = request.headers.get("Idempotency-Key", "")

        cart = get_user_cart(user=request.user)
        if cart is None or cart.is_empty:
            raise DRFValidationError("Cart is empty.")

        try:
            order = CheckoutService.process_checkout(
                cart=cart,
                user=request.user,
                shipping_address=shipping_address,
                idempotency_key=idempotency_key,
            )
        except (InsufficientStockError, DjangoValidationError) as exc:
            raise DRFValidationError(detail=getattr(exc, "messages", [str(exc)]))

        output_serializer = OrderSerializer(order)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(
        tags=["Orders"],
        summary="List user order history",
        description="Retrieve a paginated list of orders placed by the currently authenticated user.",
    ),
    retrieve=extend_schema(
        tags=["Orders"],
        summary="Get order details",
        description="Retrieve full details for a specific order belonging to the authenticated user.",
        responses={
            200: OrderSerializer,
            404: OpenApiResponse(description="Order not found or does not belong to the user"),
        },
    ),
)
class OrderReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for listing and retrieving authenticated user orders.
    """

    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Order.objects.none()
        return list_user_orders(user=self.request.user)
