"""
Order URL patterns for E-Commerce Order & Inventory Engine.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.orders.views import CheckoutAPIView, OrderReadOnlyViewSet

app_name = "orders"

router = DefaultRouter()
router.register("", OrderReadOnlyViewSet, basename="order")

urlpatterns = [
    path("checkout/", CheckoutAPIView.as_view(), name="order-checkout"),
    path("", include(router.urls)),
]
