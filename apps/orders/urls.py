"""
Order URL patterns for E-Commerce Order & Inventory Engine.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.orders.views import CheckoutAPIView, OrderInvoiceAPIView, OrderReadOnlyViewSet
from apps.payments.views import OrderPaymentAPIView

app_name = "orders"

router = DefaultRouter()
router.register("", OrderReadOnlyViewSet, basename="order")

urlpatterns = [
    path("checkout/", CheckoutAPIView.as_view(), name="order-checkout"),
    path("<uuid:order_id>/pay/", OrderPaymentAPIView.as_view(), name="order-pay"),
    path("<uuid:order_id>/invoice/", OrderInvoiceAPIView.as_view(), name="order-invoice"),
    path("", include(router.urls)),
]
