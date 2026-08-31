"""
Payment serializers for DRF API views and simulated payment processing.
"""

from rest_framework import serializers

from apps.payments.models import PaymentTransaction


class PaymentSimulationInputSerializer(serializers.Serializer):
    """
    Input serializer for triggering simulated payment.
    """

    simulate_success = serializers.BooleanField(
        default=True,
        required=False,
        help_text="If True, simulates a successful payment (PAID). If False, simulates payment decline (FAILED) and triggers compensation restocking.",
    )
    failure_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="Card declined by issuing bank.",
        help_text="Custom decline reason if simulate_success=False.",
    )
    payment_method = serializers.CharField(
        required=False,
        allow_blank=True,
        default="SIMULATED_CARD",
        help_text="Optional payment method identifier.",
    )


class PaymentTransactionSerializer(serializers.ModelSerializer):
    """
    Output serializer for full PaymentTransaction details.
    """

    order_id = serializers.UUIDField(source="order.id", read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "order_id",
            "amount",
            "status",
            "simulated_gateway_ref",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields
