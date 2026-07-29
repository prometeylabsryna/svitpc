"""Full Brain catalog availability sync (stocks/available/is_archive → stock)."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db.models import Q

from .category_filter import (
    allowed_brain_top_categories,
    allowed_local_category_subtree_pks,
    filter_brain_products_queryset,
)
from .client import products_page_limit
from .services import (
    brain_catalog_visible,
    brain_hide_out_of_stock_enabled,
    brain_shelf_prices,
    brain_stock_from_detail,
)

if TYPE_CHECKING:
    from apps.catalog.models import Product
    from apps.integrations.brain.client import BrainAPIClient

logger = logging.getLogger(__name__)


def _brain_products_by_external_ids(
    ext_ids: list[str],
    allowed_local_pks: frozenset[int],
) -> dict[str, Product]:
    """Load only the products for the CURRENT API page (not the whole catalog).

    Раніше тут будувалась мапа ВСІХ Brain-товарів одним запитом — на великому
    каталозі (десятки/сотні тисяч рядків) цей dict Django model-інстансів
    міг сам займати сотні МБ Python-пам'яті на 2GB сервері, паралельно з
    іншими воркерами/gunicorn/postgres/redis. Тепер вантажимо лише товари
    сторінки API (типово ~page_limit штук) — стара мапа звільняється GC після
    кожної сторінки замість того, щоб жити в пам'яті всю задачу.
    """
    if not ext_ids or not allowed_local_pks:
        return {}
    from apps.catalog.models import Product

    qs = (
        Product.objects.filter(source=Product.SOURCE_BRAIN, external_id__in=ext_ids)
        .filter(categories__in=allowed_local_pks)
        .distinct()
        .only(
            "pk",
            "external_id",
            "stock",
            "is_visible",
            "hide_if_out_of_stock",
            "price",
            "old_price",
            "purchase_price",
        )
    )
    return {p.external_id: p for p in qs}


def _apply_availability(
    product: Product,
    stock: int,
    hide: bool,
    shelf: Decimal,
    old_price: Decimal | None,
    wholesale: Decimal,
    *,
    dry_run: bool,
) -> bool:
    """Align stock/visibility and — when Brain returned a usable price — price too.

    Ціну оновлюємо лише коли `shelf > 0` (валідний прайс від Brain), так само
    як у `apply_detail_to_product`/`_sync_products_impl`: порожній/нульовий
    `shelf` у відповіді listing-ендпоінта не повинен затирати вже коректну
    ціну товару нулем. Це той самий фікс "гарячого" оновлення ціни, який
    інакше залежав ЛИШЕ від ненадійного `modified_products` фіда Brain
    (sync_prices, 4х/добу) — тут ціна звіряється при кожному проході повного
    списку категорії (частіше й незалежно від того фіда).
    """
    visible = brain_catalog_visible(stock=stock, shelf=shelf, hide_if_out_of_stock=hide)
    update_price = shelf > 0
    price_unchanged = (
        not update_price
        or (
            product.price == shelf
            and product.old_price == old_price
            and product.purchase_price == (wholesale if wholesale > 0 else None)
        )
    )
    unchanged = (
        product.stock == stock
        and product.is_visible == visible
        and product.hide_if_out_of_stock == hide
        and price_unchanged
    )
    if unchanged:
        return False
    if dry_run:
        return True

    from apps.catalog.models import Product

    upd: dict = {
        "stock": stock,
        "hide_if_out_of_stock": hide,
        "is_visible": visible,
    }
    if update_price:
        upd["price"] = shelf
        upd["old_price"] = old_price
        upd["purchase_price"] = wholesale if wholesale > 0 else None

    Product.objects.filter(pk=product.pk).update(**upd)
    return True


def sync_all_availability_from_brain(
    client: BrainAPIClient,
    *,
    hide_missing: bool = True,
    dry_run: bool = False,
) -> dict[str, int]:
    """Walk allowed Brain category lists and align stock/visibility for linked products.

    When hide_missing is True, Brain products in allowed subtrees but absent from the
    scan are archived locally (stock=0, hidden). Products outside the whitelist are
    not touched.
    """
    from apps.catalog.models import Product

    hide_default = brain_hide_out_of_stock_enabled()
    allowed_local_pks = allowed_local_category_subtree_pks()
    seen_ids: set[str] = set()
    stats = {
        "scanned_api": 0,
        "updated": 0,
        "missing_hidden": 0,
        "still_visible_zero_stock": 0,
    }

    top_cats = allowed_brain_top_categories(client, lang="ua")

    for brain_cat in top_cats:
        cat_id = int(brain_cat["categoryID"])
        offset = 0
        limit = products_page_limit()

        while True:
            items, total = client.get_products(cat_id, offset=offset, limit=limit)
            if not items:
                break

            page_ext_ids = [
                str(int(item["productID"])) for item in items if item.get("productID")
            ]
            by_external_id = _brain_products_by_external_ids(page_ext_ids, allowed_local_pks)

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
                shelf, old_price, wholesale = brain_shelf_prices(item)
                if _apply_availability(
                    product,
                    stock,
                    hide_default,
                    shelf,
                    old_price,
                    wholesale,
                    dry_run=dry_run,
                ):
                    stats["updated"] += 1

            offset += len(items)
            if offset >= total or len(items) < limit:
                break

    if hide_missing and seen_ids and allowed_local_pks:
        missing_qs = (
            Product.objects.filter(source=Product.SOURCE_BRAIN)
            .exclude(external_id__in=["", "0"])
            .exclude(external_id__in=seen_ids)
            .filter(categories__in=allowed_local_pks)
            .filter(Q(is_visible=True) | Q(stock__gt=0))
            .distinct()
        )
        missing_count = missing_qs.count()
        stats["missing_hidden"] = missing_count
        if missing_count and not dry_run:
            missing_qs.update(
                stock=0,
                hide_if_out_of_stock=True,
                is_visible=False,
            )

    stats["still_visible_zero_stock"] = filter_brain_products_queryset(
        Product.objects.filter(
            source=Product.SOURCE_BRAIN,
            hide_if_out_of_stock=True,
            stock__lte=0,
            is_visible=True,
        )
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
