"""
URL Configuration for E-Commerce Order & Inventory Engine.
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

api_v1_patterns = [
    path("auth/", include("apps.authentication.urls", namespace="auth")),
    path("catalog/", include("apps.catalog.urls", namespace="catalog")),
    path("cart/", include("apps.cart.urls", namespace="cart")),
    path("orders/", include("apps.orders.urls", namespace="orders")),
    path("inventory/", include("apps.inventory.urls", namespace="inventory")),
    path("payments/", include("apps.payments.urls", namespace="payments")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    # OpenAPI 3.0 / Swagger Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # API v1 Versioning Root
    path("api/v1/", include((api_v1_patterns, "api_v1"))),
]
