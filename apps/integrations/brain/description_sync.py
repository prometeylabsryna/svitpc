"""Brain product content backfill — descriptions, characteristics (warranty), cursor, re-queue."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.core.cache import cache
from django.db.models import Exists, OuterRef, Q

from apps.integrations.brain.category_filter import filter_brain_products_queryset

if TYPE_CHECKING:
    from apps.catalog.models import Product
    from apps.integrations.brain.client import BrainAPIClient

logger = logging.getLogger(__name__)

BACKFILL_CHUNK = 1000
BACKFILL_REQUEUE_SECONDS = 120
CURSOR_CACHE_KEY = "brain:backfill_descriptions:pk_cursor"
CURSOR_TTL = 6 * 3600


def _warranty_attr_exists_subquery():
    from apps.catalog.models import ProductAttribute

    return ProductAttribute.objects.filter(
        product_id=OuterRef("pk"),
        attribute__name__icontains="Гарант",
    )


def brain_products_needing_content_qs():
    """Brain products missing description and/or warranty characteristic from Brain."""
    from apps.catalog.models import Product

    base = Product.objects.filter(
        source=Product.SOURCE_BRAIN,
        external_id__gt="",
    ).filter(
        Q(description_uk__isnull=True) | Q(description_uk__exact="")
        | ~Exists(_warranty_attr_exists_subquery()),
    )
    return filter_brain_products_queryset(base)


def brain_products_missing_description_qs():
    """Alias for nightly backfill queue (descriptions + warranty/options)."""
    return brain_products_needing_content_qs()


def count_brain_products_missing_description() -> int:
    return brain_products_needing_content_qs().count()


def count_brain_products_needing_content() -> int:
    return count_brain_products_missing_description()


def _product_map_from_list(products: list[Product]) -> dict[int, Product]:
    product_map: dict[int, Product] = {}
    for product in products:
        try:
            brain_id = int(product.external_id)
        except (TypeError, ValueError):
            continue
        if brain_id > 0:
            product_map[brain_id] = product
    return product_map


def fetch_backfill_chunk(*, reset_cursor: bool = False) -> list[Product]:
    """Next batch of Brain products needing content (description and/or warranty)."""
    if reset_cursor:
        cache.delete(CURSOR_CACHE_KEY)

    cursor = int(cache.get(CURSOR_CACHE_KEY, 0) or 0)
    base_qs = (
        brain_products_missing_description_qs()
        .only("pk", "external_id", "name", "description_uk")
        .order_by("pk")
    )
    if cursor > 0:
        products = list(base_qs.filter(pk__gt=cursor)[:BACKFILL_CHUNK])
        if not products:
            cache.delete(CURSOR_CACHE_KEY)
            products = list(base_qs[:BACKFILL_CHUNK])
    else:
        products = list(base_qs[:BACKFILL_CHUNK])
    return products


def advance_backfill_cursor(products: list[Product]) -> None:
    if products:
        cache.set(CURSOR_CACHE_KEY, products[-1].pk, CURSOR_TTL)


def should_requeue_backfill(
    *,
    before_remaining: int,
    after_remaining: int,
    last_pk: int,
) -> bool:
    if after_remaining <= 0 or last_pk <= 0:
        return False
    if after_remaining < before_remaining:
        return True
    return brain_products_missing_description_qs().filter(pk__gt=last_pk).exists()


def sync_descriptions_for_products(
    client: BrainAPIClient,
    products: list[Product],
) -> tuple[int, int, int]:
    from apps.integrations.brain.content_sync import backfill_descriptions_from_content

    product_map = _product_map_from_list(products)
    if not product_map:
        return 0, 0, 0
    return backfill_descriptions_from_content(client, product_map)


def run_backfill_descriptions_chunk(*, reset_cursor: bool = False) -> dict[str, int]:
    """Fetch one chunk via products/content API. Returns stats for logging."""
    from apps.integrations.brain.client import BrainAPIClient

    before_remaining = count_brain_products_missing_description()
    if before_remaining == 0:
        if reset_cursor:
            cache.delete(CURSOR_CACHE_KEY)
        return {
            "updated": 0,
            "no_desc": 0,
            "api_miss": 0,
            "before_remaining": 0,
            "after_remaining": 0,
            "processed": 0,
            "last_pk": 0,
        }

    products = fetch_backfill_chunk(reset_cursor=reset_cursor)
    if not products:
        return {
            "updated": 0,
            "no_desc": 0,
            "api_miss": 0,
            "before_remaining": before_remaining,
            "after_remaining": before_remaining,
            "processed": 0,
            "last_pk": 0,
        }

    client = BrainAPIClient()
    updated, no_desc, api_miss = sync_descriptions_for_products(client, products)
    advance_backfill_cursor(products)
    after_remaining = count_brain_products_missing_description()

    return {
        "updated": updated,
        "no_desc": no_desc,
        "api_miss": api_miss,
        "before_remaining": before_remaining,
        "after_remaining": after_remaining,
        "processed": len(products),
        "last_pk": products[-1].pk if products else 0,
    }


def schedule_backfill_descriptions_continue() -> None:
    from apps.integrations.brain.tasks import backfill_descriptions

    backfill_descriptions.apply_async(
        countdown=BACKFILL_REQUEUE_SECONDS,
        kwargs={"reset_cursor": False},
    )
