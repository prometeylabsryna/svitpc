"""Full Brain catalog availability sync (is_archive → stock / visibility)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db.models import Q

from .client import products_page_limit
from .services import (
    brain_hide_out_of_stock_enabled,
    brain_stock_from_detail,
    brain_visibility,
)

if TYPE_CHECKING:
    from apps.catalog.models import Product
    from apps.integrations.brain.client import BrainAPIClient

logger = logging.getLogger(__name__)


def _brain_product_map() -> dict[str, Product]:
    from apps.catalog.models import Product

    return {
        p.external_id: p
        for p in Product.objects.filter(source=Product.SOURCE_BRAIN)
        .exclude(external_id__in=["", "0"])
        .only("pk", "external_id", "stock", "is_visible", "hide_if_out_of_stock")
    }


def _apply_availability(product: Product, stock: int, hide: bool, *, dry_run: bool) -> bool:
    visible = brain_visibility(stock, hide)
    unchanged = (
        product.stock == stock
        and product.is_visible == visible
        and product.hide_if_out_of_stock == hide
    )
    if unchanged:
        return False
    if dry_run:
        return True

    from apps.catalog.models import Product

    Product.objects.filter(pk=product.pk).update(
        stock=stock,
        hide_if_out_of_stock=hide,
        is_visible=visible,
    )
    return True


def sync_all_availability_from_brain(
    client: BrainAPIClient,
    *,
    hide_missing: bool = True,
    dry_run: bool = False,
) -> dict[str, int]:
    """Walk Brain category lists and align stock/visibility for every linked product.

    When hide_missing is True, Brain products absent from the full catalog scan
    are archived locally (stock=0, hidden).
    """
    from apps.catalog.models import Product

    hide_default = brain_hide_out_of_stock_enabled()
    by_external_id = _brain_product_map()
    seen_ids: set[str] = set()
    stats = {
        "scanned_api": 0,
        "updated": 0,
        "missing_hidden": 0,
        "still_visible_zero_stock": 0,
    }

    all_brain_cats = client.get_all_categories(lang="ua")
    top_cats = [c for c in all_brain_cats if c.get("parentID") == 1 and c.get("realcat", 0) == 0]

    for brain_cat in top_cats:
        cat_id = int(brain_cat["categoryID"])
        offset = 0
        limit = products_page_limit()

        while True:
            items, total = client.get_products(cat_id, offset=offset, limit=limit)
            if not items:
                break

            for item in items:
                brain_id = item.get("productID")
                if not brain_id:
                    continue
                ext_id = str(int(brain_id))
                seen_ids.add(ext_id)
                stats["scanned_api"] += 1

                product = by_external_id.get(ext_id)
                if product is None:
                    continue

                stock = brain_stock_from_detail(item)
                if _apply_availability(product, stock, hide_default, dry_run=dry_run):
                    stats["updated"] += 1
                    product.stock = stock
                    product.is_visible = brain_visibility(stock, hide_default)
                    product.hide_if_out_of_stock = hide_default

            offset += len(items)
            if offset >= total or len(items) < limit:
                break

    if hide_missing and seen_ids:
        missing_qs = (
            Product.objects.filter(source=Product.SOURCE_BRAIN)
            .exclude(external_id__in=["", "0"])
            .exclude(external_id__in=seen_ids)
            .filter(Q(is_visible=True) | Q(stock__gt=0))
        )
        missing_count = missing_qs.count()
        stats["missing_hidden"] = missing_count
        if missing_count and not dry_run:
            missing_qs.update(
                stock=0,
                hide_if_out_of_stock=True,
                is_visible=False,
            )

    stats["still_visible_zero_stock"] = Product.objects.filter(
        source=Product.SOURCE_BRAIN,
        hide_if_out_of_stock=True,
        stock__lte=0,
        is_visible=True,
    ).count()

    if stats["scanned_api"] == 0 and top_cats:
        logger.error(
            "Brain sync_all_availability: no products from API — check limit/rate limits "
            "(BRAIN_PRODUCTS_PAGE_LIMIT=%s)",
            products_page_limit(),
        )

    logger.info(
        "Brain sync_all_availability: scanned=%d updated=%d missing_hidden=%d visible_zero=%d dry_run=%s",
        stats["scanned_api"],
        stats["updated"],
        stats["missing_hidden"],
        stats["still_visible_zero_stock"],
        dry_run,
    )
    return stats
