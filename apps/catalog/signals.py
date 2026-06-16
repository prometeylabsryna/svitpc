"""Catalog signals — keep product FTS index in sync."""

from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.catalog.models import Brand, Product
from apps.catalog.pricing import enforce_retail_price, reconcile_old_price
from apps.catalog.search_index import refresh_product_search_vectors, refresh_products_for_brand


@receiver(pre_save, sender=Product)
def enforce_product_retail_floor(sender, instance: Product, **kwargs) -> None:
    """Never persist a shelf price below purchase + markup (admin, imports, legacy)."""
    if not instance.purchase_price or instance.purchase_price <= 0:
        instance.old_price = reconcile_old_price(instance.price, instance.old_price)
        return

    category_ids: list[int] = []
    if instance.pk:
        category_ids = list(instance.categories.values_list("pk", flat=True))

    instance.price = enforce_retail_price(
        instance.price,
        instance.purchase_price,
        brand_id=instance.brand_id,
        category_ids=category_ids,
    )
    instance.old_price = reconcile_old_price(instance.price, instance.old_price)


@receiver(post_save, sender=Product)
def update_product_search_vector(sender, instance: Product, **kwargs) -> None:
    refresh_product_search_vectors(Product.objects.filter(pk=instance.pk))


@receiver(post_save, sender=Brand)
def update_brand_products_search_vector(sender, instance: Brand, **kwargs) -> None:
    if instance.pk:
        refresh_products_for_brand(instance.pk)
