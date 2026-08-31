"""
Django admin configuration for catalog models.
"""

from django.contrib import admin

from apps.catalog.models import Category, Product, ProductVariant


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ["sku", "variant_name", "price_override", "is_active"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "category", "base_price", "is_active", "created_at"]
    list_filter = ["is_active", "category"]
    search_fields = ["title", "slug", "description"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [ProductVariantInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ["sku", "product", "variant_name", "price_override", "effective_price", "is_active"]
    list_filter = ["is_active", "product__category"]
    search_fields = ["sku", "variant_name", "product__title"]
