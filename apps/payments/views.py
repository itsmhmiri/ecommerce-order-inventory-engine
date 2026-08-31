"""
Payment API views: Simulated payment execution and transaction history retrieval.
"""

from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.idempotency import idempotent_request
from apps.orders.selectors import get_order_by_id
from apps.payments.models import PaymentTransaction
from apps.payments.selectors import list_user_payments
from apps.payments.serializers import (
    PaymentSimulationInputSerializer,
    PaymentTransactionSerializer,
)
from apps.payments.services import PaymentSimulationService


class OrderPaymentAPIView(APIView):
    """
    Simulates payment execution for a customer's order.
    Supports idempotency keys and triggers automatic compensation restock on payment decline.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Payments"],
        summary="Simulate order payment",
        description=(
            "Execute simulated payment processing for a specific order. "
            "If simulate_success=True, transitions Order to PAID and creates a SUCCESS payment transaction. "
            "If simulate_success=False, transitions Order to FAILED and triggers an automatic compensation "
            "transaction to restock inventory."
        ),
        request=PaymentSimulationInputSerializer,
        responses={
            200: PaymentTransactionSerializer,
            400: OpenApiResponse(description="Order cannot be paid or invalid state"),
            404: OpenApiResponse(description="Order not found or does not belong to user"),
            409: OpenApiResponse(description="Concurrent payment request in progress"),
            422: OpenApiResponse(description="Idempotency key payload mismatch"),
        },
    )
    @idempotent_request
    def post(self, request: Request, order_id: UUID) -> Response:
        order = get_order_by_id(order_id=order_id, user=request.user)
        if order is None:
            raise NotFound("Order not found.")

        input_serializer = PaymentSimulationInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        simulate_success = input_serializer.validated_data.get("simulate_success", True)
        failure_reason = input_serializer.validated_data.get("failure_reason", "")

        try:
            payment = PaymentSimulationService.process_payment(
                order=order,
                simulate_success=simulate_success,
                failure_reason=failure_reason,
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(detail=getattr(exc, "messages", [str(exc)]))

        output_serializer = PaymentTransactionSerializer(payment)
        return Response(output_serializer.data, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        tags=["Payments"],
        summary="List user payment transactions",
        description="Retrieve history of payment transactions for the authenticated user's orders.",
    ),
    retrieve=extend_schema(
        tags=["Payments"],
        summary="Get payment transaction details",
        description="Retrieve details for a specific payment transaction belonging to the authenticated user.",
        responses={
            200: PaymentTransactionSerializer,
            404: OpenApiResponse(description="Payment transaction not found"),
        },
    ),
)
class PaymentReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for listing and retrieving payment transactions for the authenticated user.
    """

    queryset = PaymentTransaction.objects.all()
    serializer_class = PaymentTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return PaymentTransaction.objects.none()
        return list_user_payments(user=self.request.user)
