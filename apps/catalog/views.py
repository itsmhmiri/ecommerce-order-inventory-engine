"""
Catalog views: Read-only API endpoints for Categories and Products.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import permissions, viewsets
from apps.catalog.selectors import list_active_categories, list_active_products, get_product_by_slug
from apps.catalog.serializers import CategorySerializer, ProductSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Catalog"],
        summary="List all active categories",
        description="Retrieve a list of all active product categories.",
    ),
    retrieve=extend_schema(
        tags=["Catalog"],
        summary="Get category details by slug",
        description="Retrieve specific active category details by unique slug.",
    ),
)
class CategoryReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only endpoint for browsing product categories.
    """
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        return list_active_categories()


@extend_schema_view(
    list=extend_schema(
        tags=["Catalog"],
        summary="List active products with variants and stock",
        description="Retrieve paginated products with nested variants and available inventory quantities.",
        parameters=[
            OpenApiParameter(
                name="category",
                type=str,
                description="Filter products by category slug",
                required=False,
            )
        ],
    ),
    retrieve=extend_schema(
        tags=["Catalog"],
        summary="Get product details by slug",
        description="Retrieve full product details including variants and live inventory by slug.",
    ),
)
class ProductReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only endpoint for products with nested SKU variants and stock levels.
    """
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        category_slug = self.request.query_params.get("category")
        return list_active_products(category_slug=category_slug)
