"""
URL configuration for catalog app.
"""

from rest_framework.routers import DefaultRouter
from apps.catalog.views import CategoryReadOnlyViewSet, ProductReadOnlyViewSet

app_name = "catalog"

router = DefaultRouter()
router.register(r"categories", CategoryReadOnlyViewSet, basename="category")
router.register(r"products", ProductReadOnlyViewSet, basename="product")

urlpatterns = router.urls
