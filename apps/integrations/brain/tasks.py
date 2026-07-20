"""Celery tasks for Brain API synchronization."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db.models import Q

from apps.integrations.heavy_sync import heavy_catalog_sync_lock, skip_if_heavy_sync_running

from .category_filter import (
    allowed_brain_top_categories,
    brain_product_allowed_for_sync,
    build_allowed_brain_category_id_set,
    filter_brain_products_queryset,
    is_brain_detail_allowed,
)

from .services import (
    apply_detail_to_product,
    brain_catalog_visible,
    brain_hide_out_of_stock_enabled,
    brain_shelf_prices,
    brain_stock_from_detail,
    build_category_map_from_db,
    resolve_brand,
    resolve_local_category,
    sync_brain_categories,
    sync_product_options,
    sync_product_pictures,
    sync_virtual_category_mirrors,
    unique_product_slug,
    upsert_brain_product,
    upsert_product_from_detail,
)

logger = logging.getLogger(__name__)

# Batch sizes for backfill tasks (avoid long-running workers)
_BACKFILL_CHUNK = 1000
_NIGHTLY_IMAGE_CHUNK = 5000
_STALE_STOCK_CHUNK = 600
_LOCK_RETRY_SECONDS = 600

# heavy_catalog_sync_lock TTL — 4 год (14400с) — абсолютний бекстоп. soft/
# time_limit нижче нього дають задачі шанс завершити `finally` у
# heavy_catalog_sync_lock (звільнити лок, ANALYZE, інвалідація кешу) ще ДО
# того, як TTL сам протух би або hard-лімітом прибило воркер без cleanup.
# Значення — з config.settings (env-конфігуровані), щоб можна було підняти
# ліміт на сервері без релізу коду, якщо реальний нічний прогін виявиться
# довшим за дефолт (перевірити фактичну тривалість — див. коментар у settings).
def _time_limits(soft_setting_name: str, default_soft: int) -> tuple[int, int]:
    from django.conf import settings

    soft = int(getattr(settings, soft_setting_name, default_soft))
    return soft, soft + 300


_FULL_SYNC_SOFT_TIME_LIMIT, _FULL_SYNC_TIME_LIMIT = _time_limits(
    "BRAIN_SYNC_PRODUCTS_SOFT_TIME_LIMIT", 3 * 3600,
)
_IMAGES_SOFT_TIME_LIMIT, _IMAGES_TIME_LIMIT = _time_limits(
    "BRAIN_SYNC_IMAGES_SOFT_TIME_LIMIT", 2 * 3600,
)
_AVAILABILITY_SOFT_TIME_LIMIT, _AVAILABILITY_TIME_LIMIT = _time_limits(
    "BRAIN_SYNC_AVAILABILITY_SOFT_TIME_LIMIT", int(1.5 * 3600),
)


def _utc_since(hours: int) -> str:
    return (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def _resilient_item(task_label: str, item_id: object) -> Iterator[None]:
    """Log-and-continue for one item inside a sync loop.

    Kancmaster.sync_all вже мав таку стійкість (один битий товар не валив
    увесь фід); Brain-задачі — ні: помилка API/парсингу на одному товарі
    (посеред тисяч) раніше обривала весь nightly/денний прогін. Один битий
    товар тепер лише логується і пропускається.

    SoftTimeLimitExceeded — теж підклас Exception (не BaseException-лише),
    тож ловимо й пробрасуємо його НЕ мовчки: інакше soft_time_limit ніколи
    не зупинить цикл — таймер спрацьовує раз, generic except його "з'їв" би,
    і задача продовжила б працювати аж до hard time_limit (SIGKILL, без
    graceful cleanup лока).
    """
    try:
        yield
    except SoftTimeLimitExceeded:
        raise
    except Exception:
        logger.exception("%s: failed to sync item id=%s", task_label, item_id)


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


def _allowed_brain_category_ids(client) -> frozenset[int]:
    return build_allowed_brain_category_id_set(client, lang="ua")


# ── sync_categories ───────────────────────────────────────────────────────────

@shared_task
def sync_categories() -> None:
    """Sync Brain category tree (runs several times per day)."""
    if skip_if_heavy_sync_running(sync_categories, "Brain sync_categories"):
        return
    client = _brain_client()
    cat_map = sync_brain_categories(client)
    # Virtual (realcat>0) Brain-вузли (напр. "SSD диски" під "Комплектуючі
    # до ПК" — алiас "Внутрішніх SSD" під ноутбуками) не входять у cat_map
    # (sync_brain_categories свідомо будує лише дерево РЕАЛЬНИХ категорій) —
    # окремо дзеркалимо товари в локальні "дзеркальні" категорії, інакше
    # такі розділи назавжди лишаються порожніми на сайті.
    mirrored = sync_virtual_category_mirrors(client, cat_map)
    logger.info(
        "Brain sync_categories done: %d categories mapped, %d mirror links added",
        len(cat_map),
        mirrored,
    )


# ── sync_products ─────────────────────────────────────────────────────────────

@shared_task(soft_time_limit=_FULL_SYNC_SOFT_TIME_LIMIT, time_limit=_FULL_SYNC_TIME_LIMIT)
def sync_products() -> None:
    """Full nightly sync: categories → vendors → products → options → images."""
    with heavy_catalog_sync_lock("brain_products") as acquired:
        if not acquired:
            sync_products.apply_async(countdown=_LOCK_RETRY_SECONDS)
            logger.warning(
                "Brain sync_products: lock busy, retry in %ss",
                _LOCK_RETRY_SECONDS,
            )
            return
        _sync_products_impl()
    sync_brain_images_nightly.apply_async(countdown=30)


def _sync_products_impl() -> None:
    from django.db import transaction
    from django.utils.text import slugify as _slug

    from apps.catalog.models import Product
    from .client import products_page_limit

    client = _brain_client()
    cat_map = sync_brain_categories(client)
    vendor_map = client.get_all_vendors()
    all_brain_cats = client.get_all_categories(lang="ua")
    top_cats = allowed_brain_top_categories(client, lang="ua")
    allowed_brain_ids = build_allowed_brain_category_id_set(client, lang="ua")
    hide_default = brain_hide_out_of_stock_enabled()

    for brain_cat in top_cats:
        cat_id = int(brain_cat["categoryID"])
        offset = 0
        limit = products_page_limit()

        while True:
            items, total = client.get_products(cat_id, offset=offset, limit=limit)
            if not items:
                break

            page_needs_desc: list[Product] = []

            for item in items:
                brain_id = item.get("productID")
                from apps.catalog.ru_localization import localize_ru_to_uk

                name = localize_ru_to_uk((item.get("name") or "").strip())
                if not brain_id or not name:
                    continue
                if not is_brain_detail_allowed(item, allowed_brain_ids):
                    continue

                with _resilient_item("Brain sync_products", brain_id):
                    brain_id = int(brain_id)
                    local_cat = resolve_local_category(
                        item,
                        cat_map,
                        fallback_cat_id=cat_id,
                    )
                    brand = resolve_brand(item, vendor_map)

                    shelf, old_price, wholesale_raw = brain_shelf_prices(item)
                    stock = brain_stock_from_detail(item)
                    sku = (item.get("articul") or item.get("product_code") or "").strip()
                    slug_base = _slug(name, allow_unicode=True) or f"brain-p-{brain_id}"
                    slug = unique_product_slug(slug_base, brain_id)
                    from apps.catalog.gallery import normalize_brain_image_url

                    main_img = normalize_brain_image_url(
                        item.get("medium_image") or item.get("large_image") or "",
                    )
                    visible = brain_catalog_visible(
                        stock=stock,
                        shelf=shelf,
                        hide_if_out_of_stock=hide_default,
                    )

                    with transaction.atomic():
                        product, created = upsert_brain_product(
                            brain_id,
                            {
                                "name": name,
                                "slug": slug,
                                "brand": brand,
                                "price": shelf,
                                "old_price": old_price,
                                "purchase_price": wholesale_raw if wholesale_raw > 0 else None,
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
                            page_needs_desc.append(product)
                        if created or not main_img:
                            sync_product_pictures(client, product, brain_id, name)

            if page_needs_desc:
                from apps.integrations.brain.description_sync import sync_descriptions_for_products

                page_label = f"cat={cat_id} offset={offset}"
                with _resilient_item("Brain sync_products: description batch", page_label):
                    u, nd, miss = sync_descriptions_for_products(client, page_needs_desc)
                    if u:
                        logger.info(
                            "Brain sync_products: descriptions page cat=%s offset=%s updated=%d",
                            cat_id,
                            offset,
                            u,
                        )

            offset += len(items)
            if offset >= total or len(items) < limit:
                break

    logger.info(
        "Brain sync_products completed: %d allowed top categories processed (of %d total)",
        len(top_cats),
        len([c for c in all_brain_cats if c.get("parentID") == 1 and c.get("realcat", 0) == 0]),
    )

    # Усі товари реальних категорій щойно оновлені вище — саме тут дзеркала
    # (SSD-диски тощо, cat_map з realcat не будує) отримають найповніший і
    # найсвіжіший набір товарів за ніч. sync_categories() (декілька разів на
    # день) теж викликає це, але з можливо ще не оновленими товарами дня.
    mirrored = sync_virtual_category_mirrors(client, cat_map)
    logger.info("Brain sync_products: %d virtual-category mirror links added", mirrored)

    from apps.integrations.brain.description_sync import count_brain_products_missing_description

    if count_brain_products_missing_description() > 0:
        backfill_descriptions.apply_async(countdown=90, kwargs={"reset_cursor": True})
        logger.info("Brain sync_products: queued description backfill (reset cursor)")


# ── sync_prices ───────────────────────────────────────────────────────────────

@shared_task
def sync_prices() -> None:
    """Sync prices (+ brand/category when present) for recently modified products."""
    if skip_if_heavy_sync_running(sync_prices, "Brain sync_prices"):
        return
    from apps.catalog.models import Product

    client = _brain_client()
    vendor_map = client.get_all_vendors()
    cat_map = build_category_map_from_db(client)
    allowed_ids = _allowed_brain_category_ids(client)

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
        with _resilient_item("Brain sync_prices", brain_id):
            detail = client.get_product(brain_id)
            if not detail:
                continue
            if not brain_product_allowed_for_sync(product, detail, allowed_ids):
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
                force_hide_flag=True,
            ):
                updated += 1

    hidden_zero = Product.objects.filter(
        source=Product.SOURCE_BRAIN,
        price__lte=0,
        is_visible=True,
    )
    hidden_zero = filter_brain_products_queryset(hidden_zero).update(is_visible=False)

    logger.info(
        "Brain sync_prices done: %d updated / %d modified, hid_zero_price=%d",
        updated,
        len(modified_ids),
        hidden_zero,
    )


# ── sync_stock ────────────────────────────────────────────────────────────────

@shared_task
def sync_stock() -> None:
    """Sync availability (is_archive) and visibility for modified products."""
    if skip_if_heavy_sync_running(sync_stock, "Brain sync_stock"):
        return
    client = _brain_client()
    vendor_map = client.get_all_vendors()
    cat_map = build_category_map_from_db(client)
    allowed_ids = _allowed_brain_category_ids(client)

    modified_ids = client.get_modified_since(_utc_since(5), limit=10000)
    if not modified_ids:
        logger.info("Brain sync_stock: no modified products")
        return

    products = _products_by_external_ids(modified_ids)
    updated = 0
    for brain_id in modified_ids:
        product = products.get(str(brain_id))
        if not product:
            continue
        with _resilient_item("Brain sync_stock", brain_id):
            detail = client.get_product(brain_id)
            if not detail:
                continue
            if not brain_product_allowed_for_sync(product, detail, allowed_ids):
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
    if skip_if_heavy_sync_running(sync_options, "Brain sync_options"):
        return
    client = _brain_client()
    allowed_ids = _allowed_brain_category_ids(client)
    modified_ids = client.get_modified_since(_utc_since(8), limit=10000, mod_type="options")
    updated = 0
    if modified_ids:
        products = _products_by_external_ids(modified_ids)
        for brain_id in modified_ids:
            product = products.get(str(brain_id))
            if not product:
                continue
            with _resilient_item("Brain sync_options", brain_id):
                if not brain_product_allowed_for_sync(product, None, allowed_ids):
                    continue
                sync_product_options(client, product, brain_id)
                updated += 1
        logger.info("Brain sync_options done: %d products", updated)
    else:
        logger.info("Brain sync_options: nothing changed in Brain")

    from apps.integrations.brain.description_sync import count_brain_products_needing_content

    if count_brain_products_needing_content() > 0:
        backfill_descriptions.apply_async(countdown=60, kwargs={"reset_cursor": False})
        logger.info("Brain sync_options: queued content backfill (warranty/descriptions)")


@shared_task
def sync_images() -> None:
    if skip_if_heavy_sync_running(sync_images, "Brain sync_images"):
        return
    _sync_images_impl(since_hours=8)


def _sync_images_impl(*, since_hours: int) -> None:
    client = _brain_client()
    allowed_ids = _allowed_brain_category_ids(client)
    modified_ids = client.get_modified_since(_utc_since(since_hours), limit=10000, mod_type="images")
    if not modified_ids:
        logger.info("Brain sync_images: nothing changed")
        return

    products = _products_by_external_ids(modified_ids)
    updated = 0
    for brain_id in modified_ids:
        product = products.get(str(brain_id))
        if not product:
            continue
        with _resilient_item("Brain sync_images", brain_id):
            if not brain_product_allowed_for_sync(product, None, allowed_ids):
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

                Product.objects.filter(pk=product.pk).update(
                    image_url=main_img, has_display_image=True,
                )
            sync_product_pictures(client, product, brain_id, product.name)
            updated += 1

    logger.info("Brain sync_images done: %d products", updated)


@shared_task(soft_time_limit=_IMAGES_SOFT_TIME_LIMIT, time_limit=_IMAGES_TIME_LIMIT)
def sync_brain_images_nightly() -> None:
    """Once per night: pull missing photos and apply image changes from Brain."""
    with heavy_catalog_sync_lock("brain_images") as acquired:
        if not acquired:
            sync_brain_images_nightly.apply_async(countdown=_LOCK_RETRY_SECONDS)
            logger.warning(
                "Brain sync_images nightly: lock busy, retry in %ss",
                _LOCK_RETRY_SECONDS,
            )
            return
        _backfill_images_impl(chunk=_NIGHTLY_IMAGE_CHUNK)
        _sync_images_impl(since_hours=24)
    sync_all_availability.apply_async(kwargs={"hide_missing": True}, countdown=30)


# ── sync_new_products ─────────────────────────────────────────────────────────

@shared_task
def sync_new_products() -> None:
    """Import newly added Brain products (between nightly full syncs)."""
    if skip_if_heavy_sync_running(sync_new_products, "Brain sync_new_products"):
        return
    client = _brain_client()
    vendor_map = client.get_all_vendors()
    cat_map = build_category_map_from_db(client)
    allowed_ids = _allowed_brain_category_ids(client)

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
        with _resilient_item("Brain sync_new_products", brain_id):
            detail = client.get_product(brain_id)
            if not detail:
                continue
            if not is_brain_detail_allowed(detail, allowed_ids):
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
    if skip_if_heavy_sync_running(backfill_metadata, "Brain backfill_metadata"):
        return
    from apps.catalog.models import Product

    client = _brain_client()
    vendor_map = client.get_all_vendors()
    cat_map = build_category_map_from_db(client)

    qs = filter_brain_products_queryset(
        Product.objects.filter(source=Product.SOURCE_BRAIN, external_id__gt="")
        .filter(brand__isnull=True)
    )
    qs = (
        qs.only("pk", "external_id", "name", "brand_id", "stock", "hide_if_out_of_stock")
        .order_by("pk")[:_BACKFILL_CHUNK]
    )

    updated = 0
    for product in qs:
        try:
            brain_id = int(product.external_id)
        except (TypeError, ValueError):
            continue
        with _resilient_item("Brain backfill_metadata", brain_id):
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

    remaining = filter_brain_products_queryset(
        Product.objects.filter(
            source=Product.SOURCE_BRAIN,
            external_id__gt="",
            brand__isnull=True,
        )
    ).count()
    logger.info(
        "Brain backfill_metadata: %d updated, ~%d without brand remain",
        updated,
        remaining,
    )


@shared_task(soft_time_limit=1800, time_limit=2100)
def backfill_descriptions(reset_cursor: bool = False) -> None:
    """Fill description_uk via POST /products/content (OWN_MODE batch API)."""
    if skip_if_heavy_sync_running(
        backfill_descriptions,
        "Brain backfill_descriptions",
        kwargs={"reset_cursor": reset_cursor},
    ):
        return
    from apps.integrations.brain.description_sync import (
        BACKFILL_REQUEUE_SECONDS,
        run_backfill_descriptions_chunk,
        schedule_backfill_descriptions_continue,
        should_requeue_backfill,
    )

    stats = run_backfill_descriptions_chunk(reset_cursor=reset_cursor)
    if stats["processed"] == 0 and stats["before_remaining"] == 0:
        logger.info("Brain backfill_descriptions: nothing to update")
        return

    logger.info(
        "Brain backfill_descriptions: %d updated, %d empty from API, %d API miss, "
        "%d processed, %d without description remain (reset_cursor=%s)",
        stats["updated"],
        stats["no_desc"],
        stats["api_miss"],
        stats["processed"],
        stats["after_remaining"],
        reset_cursor,
    )

    if should_requeue_backfill(
        before_remaining=stats["before_remaining"],
        after_remaining=stats["after_remaining"],
        last_pk=stats["last_pk"],
    ):
        schedule_backfill_descriptions_continue()
        logger.info(
            "Brain backfill_descriptions: re-queued in %ss (%d remain)",
            BACKFILL_REQUEUE_SECONDS,
            stats["after_remaining"],
        )


@shared_task
def sync_description_updates() -> None:
    """Apply Brain description changes from modified_products/descriptions."""
    if skip_if_heavy_sync_running(sync_description_updates, "Brain sync_description_updates"):
        return
    from apps.catalog.models import Product
    from apps.integrations.brain.content_sync import backfill_descriptions_from_content

    client = _brain_client()
    allowed_ids = _allowed_brain_category_ids(client)
    modified_ids = client.get_modified_since(_utc_since(24), limit=10000, mod_type="descriptions")
    if not modified_ids:
        logger.info("Brain sync_description_updates: nothing changed")
        return

    products = filter_brain_products_queryset(
        Product.objects.filter(
            source=Product.SOURCE_BRAIN,
            external_id__in=[str(i) for i in modified_ids],
        )
    ).only("pk", "external_id", "name", "description_uk")

    product_map: dict[int, Product] = {}
    for product in products:
        try:
            brain_id = int(product.external_id)
        except (TypeError, ValueError):
            continue
        if brain_id > 0:
            product_map[brain_id] = product

    updated, no_desc, api_miss = backfill_descriptions_from_content(client, product_map)
    logger.info(
        "Brain sync_description_updates: %d updated, %d empty, %d miss / %d modified",
        updated,
        no_desc,
        api_miss,
        len(modified_ids),
    )


@shared_task
def backfill_images() -> None:
    """Pull Brain photos for products missing a displayable image."""
    with heavy_catalog_sync_lock("brain_backfill_images") as acquired:
        if not acquired:
            return
        _backfill_images_impl()


def _backfill_images_impl(*, chunk: int = _BACKFILL_CHUNK) -> None:
    from apps.catalog.gallery import filter_products_missing_display_image, resolve_product_image_url
    from apps.catalog.models import Product

    client = _brain_client()
    base = filter_brain_products_queryset(
        Product.objects.filter(source=Product.SOURCE_BRAIN).exclude(external_id__in=["", "0"])
    )
    qs = (
        filter_products_missing_display_image(base)
        .only("pk", "external_id", "name", "image_url", "image")
        .prefetch_related("images")
        .order_by("pk")[:chunk]
    )

    updated = 0
    for product in qs:
        try:
            brain_id = int(product.external_id)
        except (TypeError, ValueError):
            continue
        if brain_id <= 0:
            continue
        with _resilient_item("Brain backfill_images", brain_id):
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
    if skip_if_heavy_sync_running(reconcile_stale_stock, "Brain reconcile_stale_stock"):
        return
    from apps.catalog.models import Product

    client = _brain_client()
    vendor_map = client.get_all_vendors()
    cat_map = build_category_map_from_db(client)

    qs = filter_brain_products_queryset(
        Product.objects.filter(source=Product.SOURCE_BRAIN, external_id__gt="")
        .exclude(stock__in=(0, 1))
    )
    qs = (
        qs.only("pk", "external_id", "stock", "hide_if_out_of_stock")
        .order_by("pk")[:_STALE_STOCK_CHUNK]
    )

    updated = 0
    for product in qs:
        try:
            brain_id = int(product.external_id)
        except (TypeError, ValueError):
            continue
        with _resilient_item("Brain reconcile_stale_stock", brain_id):
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

    remaining = filter_brain_products_queryset(
        Product.objects.filter(source=Product.SOURCE_BRAIN, external_id__gt="")
        .exclude(stock__in=(0, 1))
    ).count()
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

    brain_qs = filter_brain_products_queryset(Product.objects.filter(source=Product.SOURCE_BRAIN))
    brain_qs.update(hide_if_out_of_stock=True)
    brain_qs.filter(stock__lte=0).update(is_visible=False)
    brain_qs.filter(
        stock__gt=0,
        price__gt=0,
        hide_if_out_of_stock=True,
    ).update(is_visible=True)
    brain_qs.filter(price__lte=0).update(is_visible=False)

    hidden = brain_qs.filter(
        hide_if_out_of_stock=True,
        stock__lte=0,
        is_visible=True,
    ).count()
    if hidden:
        logger.warning("Brain apply_hide_out_of_stock_policy: %d still visible with stock<=0", hidden)


@shared_task(soft_time_limit=_AVAILABILITY_SOFT_TIME_LIMIT, time_limit=_AVAILABILITY_TIME_LIMIT)
def sync_all_availability(hide_missing: bool = True) -> dict[str, int] | None:
    """Full availability pass — stocks/available/is_archive for Brain catalog."""
    with heavy_catalog_sync_lock("brain_availability") as acquired:
        if not acquired:
            sync_all_availability.apply_async(
                countdown=_LOCK_RETRY_SECONDS,
                kwargs={"hide_missing": hide_missing},
            )
            logger.warning(
                "Brain sync_all_availability: lock busy, retry in %ss",
                _LOCK_RETRY_SECONDS,
            )
            return None
        return _sync_all_availability_impl(hide_missing=hide_missing)


def _sync_all_availability_impl(*, hide_missing: bool) -> dict[str, int]:
    from .availability import sync_all_availability_from_brain

    client = _brain_client()
    stats = sync_all_availability_from_brain(
        client,
        hide_missing=hide_missing,
        dry_run=False,
    )
    apply_hide_out_of_stock_policy()
    return stats


@shared_task
def sync_all_incremental() -> None:
    """Manual / admin trigger: enqueue all incremental Brain sync steps as a chain.

    Кожен крок — окрема Celery-задача у своїй черзі (замість синхронного
    виконання всього ланцюжка в одному воркері: timeout/OOM-ризик, блокування
    черги на години).
    """
    from celery import chain

    chain(
        sync_categories.si(),
        sync_prices.si(),
        sync_stock.si(),
        sync_options.si(),
        sync_images.si(),
        sync_new_products.si(),
        backfill_metadata.si(),
        backfill_descriptions.si(reset_cursor=True),
        sync_description_updates.si(),
        reconcile_stale_stock.si(),
    ).apply_async()
