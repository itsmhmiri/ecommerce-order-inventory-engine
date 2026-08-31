"""
URL configuration for inventory app.
"""

from rest_framework.routers import DefaultRouter

from apps.inventory.views import InventoryLedgerViewSet

app_name = "inventory"

router = DefaultRouter()
router.register(r"ledger", InventoryLedgerViewSet, basename="ledger")

urlpatterns = router.urls
