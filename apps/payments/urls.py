"""
Payment URL patterns for E-Commerce Order & Inventory Engine.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.payments.views import PaymentReadOnlyViewSet

app_name = "payments"

router = DefaultRouter()
router.register("", PaymentReadOnlyViewSet, basename="payment")

urlpatterns = [
    path("", include(router.urls)),
]
