"""
Order Django Admin configuration.
"""

from django.contrib import admin

from apps.orders.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["variant", "sku", "product_title", "unit_price", "quantity", "subtotal"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "status", "total_amount", "total_items", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["id", "user__username", "user__email", "shipping_address"]
    readonly_fields = ["id", "total_items", "created_at", "updated_at"]
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "sku", "product_title", "unit_price", "quantity", "subtotal"]
    list_filter = ["order__status"]
    search_fields = ["order__id", "sku", "product_title"]
    readonly_fields = ["order", "variant", "sku", "product_title", "unit_price", "quantity", "subtotal"]
