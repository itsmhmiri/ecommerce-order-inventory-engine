"""
Cart Django Admin configuration.
"""

from django.contrib import admin

from apps.cart.models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ["variant", "quantity", "unit_price", "subtotal", "created_at"]
    can_delete = True


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "total_items", "total_price", "created_at", "updated_at"]
    list_filter = ["created_at"]
    search_fields = ["id", "user__username", "user__email"]
    readonly_fields = ["id", "total_items", "total_price", "created_at", "updated_at"]
    inlines = [CartItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ["id", "cart", "variant", "quantity", "unit_price", "subtotal", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["cart__id", "variant__sku", "cart__user__username"]
    readonly_fields = ["unit_price", "subtotal", "created_at", "updated_at"]
