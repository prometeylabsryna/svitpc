"""Celery tasks for Brain API synchronization."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from celery import shared_task

from .services import (
    apply_detail_to_product,
    brain_hide_out_of_stock_enabled,
    brain_sale_old_price,
    build_category_map_from_db,
    sync_brain_categories,
    sync_product_options,
    sync_product_pictures,
    upsert_product_from_detail,
)

logger = logging.getLogger(__name__)

# Batch sizes for backfill tasks (avoid long-running workers)
_BACKFILL_CHUNK = 600
_STALE_STOCK_CHUNK = 600


def _utc_since(hours: int) -> str:
    return (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


def _brain_client():
    from .client import BrainAPIClient

    return BrainAPIClient()


def _products_by_external_ids(modified_ids: list[int]) -> dict[str, "Product"]:  # type: ignore[name-defined]
    from apps.catalog.models import Product

    return {
        p.external_id: p
        for p in Product.objects.filter(
            source=Product.SOURCE_BRAIN,
            external_id__in=[str(i) for i in modified_ids],
        ).prefetch_related("categories")
    }


# ── sync_categories ───────────────────────────────────────────────────────────

@shared_task
def sync_categories() -> None:
    """Sync Brain category tree (runs several times per day)."""
    client = _brain_client()
    cat_map = sync_brain_categories(client)
    logger.info("Brain sync_categories done: %d categories mapped", len(cat_map))


# ── sync_products ─────────────────────────────────────────────────────────────

@shared_task
def sync_products() -> None:
    """Full nightly sync: categories → vendors → products → options → images."""
    from django.db import transaction
    from django.utils.text import slugify as _slug

    from apps.catalog.models import Product
    from apps.catalog.services import apply_markup
    from .services import (
        brain_stock_from_detail,
        brain_visibility,
        resolve_brand,
        resolve_local_category,
        unique_product_slug,
    )

    client = _brain_client()
    cat_map = sync_brain_categories(client)
    vendor_map = client.get_all_vendors()
    all_brain_cats = client.get_all_categories(lang="ua")
    top_cats = [c for c in all_brain_cats if c.get("parentID") == 1 and c.get("realcat", 0) == 0]
    hide_default = brain_hide_out_of_stock_enabled()

    for brain_cat in top_cats:
        cat_id = int(brain_cat["categoryID"])
        offset = 0
        limit = 1000

        while True:
            items, total = client.get_products(cat_id, offset=offset, limit=limit)
            if not items:
                break

            for item in items:
                brain_id = item.get("productID")
                from apps.catalog.ru_localization import localize_ru_to_uk

                name = localize_ru_to_uk((item.get("name") or "").strip())
                if not brain_id or not name:
                    continue

                brain_id = int(brain_id)
                local_cat = resolve_local_category(
                    item,
                    cat_map,
                    fallback_cat_id=cat_id,
                )
                brand = resolve_brand(item, vendor_map)

                from decimal import Decimal

                price_raw = Decimal(str(item.get("price_uah") or item.get("price") or 0))
                stock = brain_stock_from_detail(item)
                sku = (item.get("articul") or item.get("product_code") or "").strip()
                cat_ids = [local_cat.pk] if local_cat else []
                brand_id = brand.pk if brand else None
                final_price = apply_markup(price_raw, brand_id, cat_ids)
                old_price = brain_sale_old_price(item, price_raw, brand_id, cat_ids) if price_raw > 0 else None
                slug_base = _slug(name, allow_unicode=True) or f"brain-p-{brain_id}"
                slug = unique_product_slug(slug_base, brain_id)
                from apps.catalog.gallery import normalize_brain_image_url

                main_img = normalize_brain_image_url(
                    item.get("medium_image") or item.get("large_image") or "",
                )
                visible = brain_visibility(stock, hide_default)

                with transaction.atomic():
                    product, created = Product.objects.update_or_create(
                        source=Product.SOURCE_BRAIN,
                        external_id=str(brain_id),
                        defaults={
                            "name": name,
                            "slug": slug,
                            "brand": brand,
                            "price": final_price,
                            "old_price": old_price,
                            "purchase_price": price_raw,
                            "stock": stock,
                            "sku": sku,
                            "image_url": main_img,
                            "hide_if_out_of_stock": hide_default,
                            "is_visible": visible,
                        },
                    )
                    if local_cat:
                        product.categories.set([local_cat])
                    if created:
                        sync_product_options(client, product, brain_id)
                    if created or not main_img:
                        sync_product_pictures(client, product, brain_id, name)

            offset += len(items)
            if offset >= total or len(items) < limit:
                break

    logger.info("Brain sync_products completed: %d top categories processed", len(top_cats))

    from apps.catalog.tasks import translate_to_english

    translate_to_english.delay(what="products", with_descriptions=True)


# ── sync_prices ───────────────────────────────────────────────────────────────

@shared_task
def sync_prices() -> None:
    """Sync prices (+ brand/category when present) for recently modified products."""
    client = _brain_client()
    vendor_map = client.get_all_vendors()
    cat_map = build_category_map_from_db(client)

    modified_ids = client.get_modified_since(_utc_since(5), limit=10000)
    if not modified_ids:
        logger.info("Brain sync_prices: no modified products")
        return

    products = _products_by_external_ids(modified_ids)
    updated = 0
    for brain_id in modified_ids:
        product = products.get(str(brain_id))
        if not product:
            continue
        detail = client.get_product(brain_id)
        if not detail:
            continue
        if apply_detail_to_product(
            product,
            detail,
            vendor_map=vendor_map,
            cat_map=cat_map,
            update_price=True,
            update_stock=False,
            update_brand=True,
            update_category=True,
            force_hide_flag=True,
        ):
            updated += 1

    logger.info("Brain sync_prices done: %d updated / %d modified", updated, len(modified_ids))


# ── sync_stock ────────────────────────────────────────────────────────────────

@shared_task
def sync_stock() -> None:
    """Sync availability (is_archive) and visibility for modified products."""
    client = _brain_client()
    vendor_map = client.get_all_vendors()
    cat_map = build_category_map_from_db(client)

    modified_ids = client.get_modified_since(_utc_since(3), limit=10000)
    if not modified_ids:
        logger.info("Brain sync_stock: no modified products")
        return

    products = _products_by_external_ids(modified_ids)
    updated = 0
    for brain_id in modified_ids:
        product = products.get(str(brain_id))
        if not product:
            continue
        detail = client.get_product(brain_id)
        if not detail:
            continue
        if apply_detail_to_product(
            product,
            detail,
            vendor_map=vendor_map,
            cat_map=cat_map,
            update_price=False,
            update_stock=True,
            update_brand=True,
            update_category=False,
            force_hide_flag=True,
        ):
            updated += 1

    logger.info("Brain sync_stock done: %d updated / %d modified", updated, len(modified_ids))


# ── sync_options / sync_images ────────────────────────────────────────────────

@shared_task
def sync_options() -> None:
    client = _brain_client()
    modified_ids = client.get_modified_since(_utc_since(8), limit=10000, mod_type="options")
    if not modified_ids:
        logger.info("Brain sync_options: nothing changed")
        return

    products = _products_by_external_ids(modified_ids)
    updated = 0
    for brain_id in modified_ids:
        product = products.get(str(brain_id))
        if not product:
            continue
        sync_product_options(client, product, brain_id)
        updated += 1

    logger.info("Brain sync_options done: %d products", updated)


@shared_task
def sync_images() -> None:
    client = _brain_client()
    modified_ids = client.get_modified_since(_utc_since(8), limit=10000, mod_type="images")
    if not modified_ids:
        logger.info("Brain sync_images: nothing changed")
        return

    products = _products_by_external_ids(modified_ids)
    updated = 0
    for brain_id in modified_ids:
        product = products.get(str(brain_id))
        if not product:
            continue
        detail = client.get_product(brain_id)
        main_img = ""
        from apps.catalog.gallery import normalize_brain_image_url

        if detail:
            main_img = normalize_brain_image_url(
                detail.get("medium_image") or detail.get("large_image") or "",
            )
        if main_img:
            from apps.catalog.models import Product

            Product.objects.filter(pk=product.pk).update(image_url=main_img)
        sync_product_pictures(client, product, brain_id, product.name)
        updated += 1

    logger.info("Brain sync_images done: %d products", updated)


# ── sync_new_products ─────────────────────────────────────────────────────────

@shared_task
def sync_new_products() -> None:
    """Import newly added Brain products (between nightly full syncs)."""
    client = _brain_client()
    vendor_map = client.get_all_vendors()
    cat_map = build_category_map_from_db(client)

    new_ids = client.get_modified_since(_utc_since(7), limit=10000, mod_type="new")
    if not new_ids:
        logger.info("Brain sync_new_products: no new products")
        return

    from apps.catalog.models import Product

    existing_ids = set(
        Product.objects.filter(
            source=Product.SOURCE_BRAIN,
            external_id__in=[str(i) for i in new_ids],
        ).values_list("external_id", flat=True)
    )
    to_import = [i for i in new_ids if str(i) not in existing_ids]
    imported = 0

    for brain_id in to_import:
        detail = client.get_product(brain_id)
        if not detail:
            continue
        try:
            _, created = upsert_product_from_detail(
                client,
                brain_id,
                detail,
                vendor_map=vendor_map,
                cat_map=cat_map,
                sync_options=True,
                sync_pictures=True,
            )
            if created:
                imported += 1
        except ValueError:
            continue

    logger.info("Brain sync_new_products done: %d imported / %d new", imported, len(to_import))


# ── backfill (OC-imported products missing Brain metadata) ────────────────────

@shared_task
def backfill_metadata() -> None:
    """Fill brand/stock/category for Brain products still missing vendor mapping."""
    from apps.catalog.models import Product

    client = _brain_client()
    vendor_map = client.get_all_vendors()
    cat_map = build_category_map_from_db(client)

    qs = (
        Product.objects.filter(source=Product.SOURCE_BRAIN, external_id__gt="")
        .filter(brand__isnull=True)
        .only("pk", "external_id", "name", "brand_id", "stock", "hide_if_out_of_stock")
        .order_by("pk")[:_BACKFILL_CHUNK]
    )

    updated = 0
    for product in qs:
        try:
            brain_id = int(product.external_id)
        except (TypeError, ValueError):
            continue
        detail = client.get_product(brain_id)
        if not detail:
            continue
        if apply_detail_to_product(
            product,
            detail,
            vendor_map=vendor_map,
            cat_map=cat_map,
            update_price=True,
            update_stock=True,
            update_brand=True,
            update_category=True,
            update_image=True,
            force_hide_flag=True,
        ):
            updated += 1

    remaining = Product.objects.filter(
        source=Product.SOURCE_BRAIN,
        external_id__gt="",
        brand__isnull=True,
    ).count()
    logger.info(
        "Brain backfill_metadata: %d updated, ~%d without brand remain",
        updated,
        remaining,
    )


@shared_task
def backfill_images() -> None:
    """Pull Brain photos for products missing a displayable image."""
    from apps.catalog.gallery import filter_products_missing_display_image, resolve_product_image_url
    from apps.catalog.models import Product

    client = _brain_client()
    base = Product.objects.filter(source=Product.SOURCE_BRAIN).exclude(external_id__in=["", "0"])
    qs = (
        filter_products_missing_display_image(base)
        .only("pk", "external_id", "name", "image_url", "image")
        .prefetch_related("images")
        .order_by("pk")[:_BACKFILL_CHUNK]
    )

    updated = 0
    for product in qs:
        try:
            brain_id = int(product.external_id)
        except (TypeError, ValueError):
            continue
        if brain_id <= 0:
            continue
        sync_product_pictures(client, product, brain_id, product.name)
        product.refresh_from_db()
        if resolve_product_image_url(product):
            updated += 1

    remaining = filter_products_missing_display_image(base).count()
    logger.info(
        "Brain backfill_images: %d gained photos, ~%d still without image remain",
        updated,
        remaining,
    )


@shared_task
def reconcile_stale_stock() -> None:
    """Fix OC-imported placeholder stock (e.g. 999) using Brain is_archive."""
    from apps.catalog.models import Product

    client = _brain_client()
    vendor_map = client.get_all_vendors()
    cat_map = build_category_map_from_db(client)

    qs = (
        Product.objects.filter(source=Product.SOURCE_BRAIN, external_id__gt="")
        .exclude(stock__in=(0, 1))
        .only("pk", "external_id", "stock", "hide_if_out_of_stock")
        .order_by("pk")[:_STALE_STOCK_CHUNK]
    )

    updated = 0
    for product in qs:
        try:
            brain_id = int(product.external_id)
        except (TypeError, ValueError):
            continue
        detail = client.get_product(brain_id)
        if not detail:
            continue
        if apply_detail_to_product(
            product,
            detail,
            vendor_map=vendor_map,
            cat_map=cat_map,
            update_price=False,
            update_stock=True,
            update_brand=True,
            update_category=False,
            force_hide_flag=True,
        ):
            updated += 1

    remaining = (
        Product.objects.filter(source=Product.SOURCE_BRAIN, external_id__gt="")
        .exclude(stock__in=(0, 1))
        .count()
    )
    logger.info(
        "Brain reconcile_stale_stock: %d fixed, ~%d non-binary stock remain",
        updated,
        remaining,
    )


@shared_task
def apply_hide_out_of_stock_policy() -> None:
    """Enable hide_if_out_of_stock on all Brain products and fix visibility."""
    from apps.catalog.models import Product

    if not brain_hide_out_of_stock_enabled():
        return

    Product.objects.filter(source=Product.SOURCE_BRAIN).update(hide_if_out_of_stock=True)
    Product.objects.filter(
        source=Product.SOURCE_BRAIN,
        stock__lte=0,
    ).update(is_visible=False)
    Product.objects.filter(
        source=Product.SOURCE_BRAIN,
        stock__gt=0,
        hide_if_out_of_stock=True,
    ).update(is_visible=True)

    hidden = Product.objects.filter(
        source=Product.SOURCE_BRAIN,
        hide_if_out_of_stock=True,
        stock__lte=0,
        is_visible=True,
    ).count()
    if hidden:
        logger.warning("Brain apply_hide_out_of_stock_policy: %d still visible with stock<=0", hidden)


@shared_task
def sync_all_incremental() -> None:
    """Manual / admin trigger: run all incremental Brain sync steps in sequence."""
    sync_categories()
    sync_prices()
    sync_stock()
    sync_options()
    sync_images()
    sync_new_products()
    backfill_metadata()
    reconcile_stale_stock()
