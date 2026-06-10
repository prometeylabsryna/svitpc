"""Catalog signals — keep product FTS index in sync."""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.catalog.models import Brand, Product
from apps.catalog.search_index import refresh_product_search_vectors, refresh_products_for_brand


@receiver(post_save, sender=Product)
def update_product_search_vector(sender, instance: Product, **kwargs) -> None:
    refresh_product_search_vectors(Product.objects.filter(pk=instance.pk))


@receiver(post_save, sender=Brand)
def update_brand_products_search_vector(sender, instance: Brand, **kwargs) -> None:
    if instance.pk:
        refresh_products_for_brand(instance.pk)
