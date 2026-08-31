"""
Cart URL patterns for E-Commerce Order & Inventory Engine.
"""

from django.urls import path
from apps.cart.views import CartDetailView, CartItemCreateView, CartItemDetailView

app_name = "cart"

urlpatterns = [
    path("", CartDetailView.as_view(), name="cart-detail"),
    path("items/", CartItemCreateView.as_view(), name="cart-item-create"),
    path("items/<int:item_id>/", CartItemDetailView.as_view(), name="cart-item-detail"),
]
