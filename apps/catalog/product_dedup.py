"""Merge duplicate integration products (same source + external_id)."""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Count

logger = logging.getLogger(__name__)


def _pick_canonical(products: list) -> object:
    """Prefer most viewed, then newest, then lowest pk."""
    return sorted(
        products,
        key=lambda p: (p.viewed or 0, p.date_modified, -p.pk),
        reverse=True,
    )[0]


def merge_product_into(canonical, duplicate) -> None:
    """Move relations from duplicate onto canonical, then delete duplicate."""
    from apps.catalog.models import ProductAttribute, ProductFilter, ProductImage
    from apps.orders.models import OrderItem
    from apps.promotions.models import Promotion
    from apps.reviews.models import Review
    from apps.wishlist.models import WishlistItem

    if canonical.pk == duplicate.pk:
        return

    canonical.categories.add(*duplicate.categories.all())

    max_sort = (
        ProductImage.objects.filter(product=canonical)
        .order_by("-sort_order")
        .values_list("sort_order", flat=True)
        .first()
        or 0
    )
    for offset, image in enumerate(
        ProductImage.objects.filter(product=duplicate).order_by("sort_order", "pk"),
        start=1,
    ):
        if ProductImage.objects.filter(product=canonical, sort_order=image.sort_order).exists():
            image.sort_order = max_sort + offset
        image.product = canonical
        image.save(update_fields=["product", "sort_order"])

    for row in ProductAttribute.objects.filter(product=duplicate):
        ProductAttribute.objects.update_or_create(
            product=canonical,
            attribute=row.attribute,
            defaults={"value": row.value},
        )
        row.delete()

    for row in ProductFilter.objects.filter(product=duplicate):
        ProductFilter.objects.get_or_create(product=canonical, filter=row.filter)
        row.delete()

    Review.objects.filter(product=duplicate).update(product=canonical)
    OrderItem.objects.filter(product=duplicate).update(product=canonical)

    for wish in WishlistItem.objects.filter(product=duplicate):
        if WishlistItem.objects.filter(customer=wish.customer, product=canonical).exists():
            wish.delete()
        else:
            wish.product = canonical
            wish.save(update_fields=["product"])

    dup_promos = list(Promotion.objects.filter(product=duplicate))
    if dup_promos and not Promotion.objects.filter(product=canonical).exists():
        Promotion.objects.filter(pk=dup_promos[0].pk).update(product=canonical)
        for extra in dup_promos[1:]:
            extra.delete()
    else:
        Promotion.objects.filter(product=duplicate).delete()

    duplicate.delete()


@transaction.atomic
def dedupe_source_external_id(source: str, external_id: str) -> int:
    """Merge all products with the same source/external_id. Returns rows deleted."""
    from apps.catalog.models import Product

    rows = list(
        Product.objects.filter(source=source, external_id=external_id).order_by("pk")
    )
    if len(rows) < 2:
        return 0

    canonical = _pick_canonical(rows)
    deleted = 0
    for duplicate in rows:
        if duplicate.pk == canonical.pk:
            continue
        logger.warning(
            "Merging duplicate %s product external_id=%s: keep pk=%s drop pk=%s",
            source,
            external_id,
            canonical.pk,
            duplicate.pk,
        )
        merge_product_into(canonical, duplicate)
        deleted += 1
    return deleted


def dedupe_all_integration_products() -> int:
    """Merge every duplicate (source, external_id) group. Returns rows deleted."""
    from apps.catalog.models import Product

    deleted = 0
    groups = (
        Product.objects.exclude(external_id="")
        .values("source", "external_id")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
    )
    for group in groups:
        deleted += dedupe_source_external_id(group["source"], group["external_id"])
    return deleted
