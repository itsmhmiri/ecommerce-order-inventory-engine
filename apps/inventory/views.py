"""
Inventory views: Admin-only audit ledger API endpoints.
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import permissions, viewsets

from apps.inventory.selectors import list_inventory_transactions
from apps.inventory.serializers import InventoryTransactionSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Inventory"],
        summary="View stock transaction audit trail (Admin)",
        description="Retrieve the immutable stock audit ledger history. Admin permissions required.",
        parameters=[
            OpenApiParameter(
                name="variant_id",
                type=int,
                description="Filter transactions by ProductVariant ID",
                required=False,
            ),
            OpenApiParameter(
                name="transaction_type",
                type=str,
                description="Filter by transaction type (e.g. PURCHASE_DEDUCTION, RESTOCK)",
                required=False,
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=["Inventory"],
        summary="Get stock ledger transaction by ID",
        description="Retrieve a specific audit ledger entry by ID. Admin permissions required.",
    ),
)
class InventoryLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin-only read-only viewset for inspecting the inventory audit trail.
    """
    serializer_class = InventoryTransactionSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        variant_id = self.request.query_params.get("variant_id")
        transaction_type = self.request.query_params.get("transaction_type")
        return list_inventory_transactions(
            variant_id=int(variant_id) if variant_id and variant_id.isdigit() else None,
            transaction_type=transaction_type,
        )
