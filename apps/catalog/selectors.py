"""
Catalog selectors: Read-only database query functions and aggregations.
"""

from django.db.models import QuerySet

from apps.catalog.models import Category, Product


def list_active_categories() -> QuerySet[Category]:
    """
    Returns all active categories ordered by name.
    """
    return Category.objects.filter(is_active=True).order_by("name")


def get_category_by_slug(slug: str) -> Category | None:
    """
    Retrieves a single active category by its unique slug.
    """
    return Category.objects.filter(slug=slug, is_active=True).first()


def list_active_products(category_slug: str | None = None) -> QuerySet[Product]:
    """
    Returns active products with prefetched categories, variants, and stock inventories
    to avoid N+1 queries.
    """
    qs = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .prefetch_related(
            "variants",
            "variants__inventory",
        )
        .order_by("-created_at")
    )
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    return qs


def get_product_by_slug(slug: str) -> Product | None:
    """
    Retrieves a single active product by its unique slug with all relations prefetched.
    """
    return (
        Product.objects.filter(slug=slug, is_active=True)
        .select_related("category")
        .prefetch_related(
            "variants",
            "variants__inventory",
        )
        .first()
    )
