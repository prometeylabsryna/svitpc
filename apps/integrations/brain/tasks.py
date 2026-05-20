"""Celery tasks for Brain API synchronization.

sync_products  — nightly full sync (categories → products → options → images)
sync_prices    — every 4 h  — modified products → update price via single product fetch
sync_stock     — every 2 h  — modified products → update is_archive → update stock
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from celery import shared_task
from django.utils.text import slugify

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _upsert_brand(name: str) -> "Brand":  # type: ignore[name-defined]
    from apps.catalog.models import Brand
    slug = slugify(name, allow_unicode=True) or f"brand-{abs(hash(name))}"
    brand, _ = Brand.objects.get_or_create(name=name, defaults={"slug": slug})
    return brand


def _unique_slug(base: str, brain_id: int | str, Model: type) -> str:  # noqa: N803
    from apps.catalog.models import Product
    slug = base
    counter = 1
    while (
        Model.objects.filter(slug=slug)
        .exclude(source=Product.SOURCE_BRAIN, external_id=str(brain_id))
        .exists()
    ):
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def _sync_options(client: "BrainAPIClient", product: "Product", brain_id: int) -> None:  # type: ignore[name-defined]
    """Sync product_options from Brain → ProductAttribute rows.

    Brain structure: OptionName = attribute name, ValueName = attribute value.
    We use a single AttributeGroup "Характеристики" for all Brain options.
    """
    from apps.catalog.models import Attribute, AttributeGroup, ProductAttribute

    options = client.get_product_options(brain_id, lang="ua")
    if not options:
        return

    # One shared group for all Brain characteristics
    ag, _ = AttributeGroup.objects.get_or_create(name="Характеристики")

    for opt in options:
        attr_name = (opt.get("OptionName") or "").strip()
        attr_val = (opt.get("ValueName") or "").strip()
        if not attr_name or not attr_val:
            continue
        attr, _ = Attribute.objects.get_or_create(group=ag, name=attr_name)
        ProductAttribute.objects.update_or_create(
            product=product, attribute=attr,
            defaults={"value": attr_val},
        )


def _sync_pictures(client: "BrainAPIClient", product: "Product", brain_id: int, name: str) -> None:  # type: ignore[name-defined]
    from apps.catalog.models import ProductImage
    pics = client.get_product_pictures(brain_id)
    for pic in pics:
        img_url = pic.get("medium_image") or pic.get("large_image") or ""
        if not img_url:
            continue
        priority = int(pic.get("priority", 0))
        ProductImage.objects.update_or_create(
            product=product, sort_order=priority,
            defaults={"image_url": img_url, "alt": name},
        )


# ── sync_products ─────────────────────────────────────────────────────────────

@shared_task
def sync_products() -> None:
    """Full nightly sync: categories → vendors → products → options → images."""
    from django.db import transaction
    from django.utils.text import slugify as _slug

    from apps.catalog.models import Category, Product, ProductImage
    from apps.catalog.services import apply_markup
    from .client import BrainAPIClient

    client = BrainAPIClient()

    # ── 1. Sync Brain categories to local DB ─────────────────────────────────
    all_brain_cats = client.get_all_categories(lang="ua")
    # brain_id → local Category (populated in parent-first order)
    cat_map: dict[int, Category] = {}

    # Sort: parents before children (parentID=1 are root)
    sorted_cats = sorted(all_brain_cats, key=lambda c: (c["parentID"], c["categoryID"]))

    for bc in sorted_cats:
        if bc.get("realcat", 0) > 0:
            continue  # skip virtual / alias categories
        cat_id = int(bc["categoryID"])
        name = (bc.get("name") or "").strip()
        if not name:
            continue

        slug_base = _slug(name, allow_unicode=True) or f"brain-cat-{cat_id}"
        parent_brain_id = bc.get("parentID")
        parent_local = cat_map.get(parent_brain_id) if parent_brain_id != 1 else None

        cat, _ = Category.objects.update_or_create(
            slug=slug_base,
            defaults={"name": name, "parent": parent_local, "is_active": True},
        )
        cat_map[cat_id] = cat

    # ── 2. Pre-fetch vendors (vendorID → name) ───────────────────────────────
    vendor_map: dict[int, str] = client.get_all_vendors()

    # ── 3. Iterate top-level categories, paginate products ──────────────────
    top_cats = [c for c in all_brain_cats if c.get("parentID") == 1 and c.get("realcat", 0) == 0]

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
                name = (item.get("name") or "").strip()
                if not brain_id or not name:
                    continue

                brain_id = int(brain_id)

                # Resolve local category from product's own categoryID
                prod_cat_id = item.get("categoryID")
                local_cat = cat_map.get(int(prod_cat_id)) if prod_cat_id else cat_map.get(cat_id)

                # Brand from vendor map
                brand = None
                vendor_id = item.get("vendorID")
                if vendor_id:
                    vendor_name = vendor_map.get(int(vendor_id))
                    if vendor_name:
                        brand = _upsert_brand(vendor_name)

                # Price (price_uah = UAH price from Brain)
                price_raw = Decimal(str(item.get("price_uah") or item.get("price") or 0))
                is_archive = bool(item.get("is_archive", False))
                stock = 0 if is_archive else 1
                sku = (item.get("articul") or item.get("product_code") or "").strip()

                cat_ids = [local_cat.pk] if local_cat else []
                final_price = apply_markup(price_raw, brand.pk if brand else None, cat_ids)

                slug_base = _slug(name, allow_unicode=True) or f"brain-p-{brain_id}"
                slug = _unique_slug(slug_base, brain_id, Product)

                main_img = item.get("medium_image") or item.get("large_image") or ""

                with transaction.atomic():
                    product, created = Product.objects.update_or_create(
                        source=Product.SOURCE_BRAIN,
                        external_id=str(brain_id),
                        defaults={
                            "name": name,
                            "slug": slug,
                            "brand": brand,
                            "price": final_price,
                            "purchase_price": price_raw,
                            "stock": stock,
                            "sku": sku,
                            "image_url": main_img,
                            # is_visible set below — new products get stock-based visibility;
                            # existing products respect their hide_if_out_of_stock flag
                        },
                    )

                    # Visibility: new → stock-based; existing → respect hide_if_out_of_stock
                    new_visible = stock > 0
                    if created:
                        Product.objects.filter(pk=product.pk).update(is_visible=new_visible)
                    elif product.hide_if_out_of_stock and product.is_visible != new_visible:
                        Product.objects.filter(pk=product.pk).update(is_visible=new_visible)

                    # Category: use set() so relocated products drop stale categories
                    if local_cat:
                        product.categories.set([local_cat])

                    # Always update main image
                    if main_img:
                        ProductImage.objects.update_or_create(
                            product=product, sort_order=0,
                            defaults={"image_url": main_img, "alt": name},
                        )

                    # For new products: fetch full options and all pictures
                    if created:
                        _sync_options(client, product, brain_id)
                        _sync_pictures(client, product, brain_id, name)

            offset += len(items)
            if offset >= total or len(items) < limit:
                break

    logger.info("Brain sync_products completed: %d top categories processed", len(top_cats))


# ── sync_prices ───────────────────────────────────────────────────────────────

@shared_task
def sync_prices() -> None:
    """Sync prices for products modified in the last 5 hours.

    Uses /modified_products/{SID} to get changed IDs → fetches each product
    via /product/{productID}/{SID} → applies markup → updates price.
    """
    from apps.catalog.models import Product
    from apps.catalog.services import apply_markup
    from .client import BrainAPIClient

    client = BrainAPIClient()

    since = (datetime.utcnow() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")
    modified_ids = client.get_modified_since(since, limit=10000)

    if not modified_ids:
        logger.info("Brain sync_prices: no modified products since %s", since)
        return

    # Only process IDs we actually have in our DB
    existing = dict(
        Product.objects.filter(
            source=Product.SOURCE_BRAIN,
            external_id__in=[str(i) for i in modified_ids],
        ).values_list("external_id", "pk")
    )
    # Prefetch categories for markup
    from django.db.models import Prefetch
    pk_to_cats: dict[int, list[int]] = {
        p.pk: list(p.categories.values_list("pk", flat=True))
        for p in Product.objects.filter(pk__in=existing.values()).prefetch_related("categories")
    }
    brand_map: dict[int, int | None] = dict(
        Product.objects.filter(pk__in=existing.values()).values_list("pk", "brand_id")
    )

    updated = 0
    for brain_id in modified_ids:
        pk = existing.get(str(brain_id))
        if pk is None:
            continue

        detail = client.get_product(brain_id)
        if not detail:
            continue

        price_raw = Decimal(str(detail.get("price_uah") or detail.get("price") or 0))
        if price_raw <= 0:
            continue

        cat_ids = pk_to_cats.get(pk, [])
        brand_id = brand_map.get(pk)
        final_price = apply_markup(price_raw, brand_id, cat_ids)

        Product.objects.filter(pk=pk).update(price=final_price, purchase_price=price_raw)
        updated += 1

    logger.info("Brain sync_prices done: %d updated out of %d modified", updated, len(modified_ids))


# ── sync_stock ────────────────────────────────────────────────────────────────

@shared_task
def sync_stock() -> None:
    """Sync stock/availability for products modified in the last 3 hours.

    Brain API does not expose warehouse quantities for this account level.
    Uses is_archive field: False → stock=1 (orderable), True → stock=0.
    Respects the hide_if_out_of_stock product flag.
    """
    from apps.catalog.models import Product
    from .client import BrainAPIClient

    client = BrainAPIClient()

    since = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    modified_ids = client.get_modified_since(since, limit=10000)

    if not modified_ids:
        logger.info("Brain sync_stock: no modified products since %s", since)
        return

    prod_meta: dict[str, tuple[int, bool]] = {
        row["external_id"]: (row["pk"], row["hide_if_out_of_stock"])
        for row in Product.objects.filter(
            source=Product.SOURCE_BRAIN,
            external_id__in=[str(i) for i in modified_ids],
        ).values("external_id", "pk", "hide_if_out_of_stock")
    }

    updated = 0
    for brain_id in modified_ids:
        meta = prod_meta.get(str(brain_id))
        if meta is None:
            continue
        pk, hide_if_out = meta

        detail = client.get_product(brain_id)
        if not detail:
            continue

        is_archive = bool(detail.get("is_archive", False))
        stock = 0 if is_archive else 1

        upd: dict = {"stock": stock}
        if hide_if_out:
            upd["is_visible"] = stock > 0

        Product.objects.filter(pk=pk).update(**upd)
        updated += 1

    logger.info("Brain sync_stock done: %d updated out of %d modified", updated, len(modified_ids))


# ── sync_options ──────────────────────────────────────────────────────────────

@shared_task
def sync_options() -> None:
    """Sync characteristics for products whose options changed since yesterday.

    Uses /modified_products/options/{SID} to avoid re-fetching all 87K products.
    """
    from apps.catalog.models import Product
    from .client import BrainAPIClient

    client = BrainAPIClient()
    since = (datetime.utcnow() - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
    modified_ids = client.get_modified_since(since, limit=10000, mod_type="options")

    if not modified_ids:
        logger.info("Brain sync_options: nothing changed")
        return

    prod_map: dict[str, int] = dict(
        Product.objects.filter(
            source=Product.SOURCE_BRAIN,
            external_id__in=[str(i) for i in modified_ids],
        ).values_list("external_id", "pk")
    )

    updated = 0
    for brain_id in modified_ids:
        if str(brain_id) not in prod_map:
            continue
        product = Product.objects.get(pk=prod_map[str(brain_id)])
        _sync_options(client, product, brain_id)
        updated += 1

    logger.info("Brain sync_options done: %d products updated", updated)


# ── sync_images ───────────────────────────────────────────────────────────────

@shared_task
def sync_images() -> None:
    """Sync gallery images for products whose pictures changed since yesterday.

    Uses /modified_products/images/{SID} to fetch only changed ones.
    """
    from apps.catalog.models import Product
    from .client import BrainAPIClient

    client = BrainAPIClient()
    since = (datetime.utcnow() - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
    modified_ids = client.get_modified_since(since, limit=10000, mod_type="images")

    if not modified_ids:
        logger.info("Brain sync_images: nothing changed")
        return

    prod_qs = Product.objects.filter(
        source=Product.SOURCE_BRAIN,
        external_id__in=[str(i) for i in modified_ids],
    ).only("pk", "external_id", "name")

    updated = 0
    for product in prod_qs:
        _sync_pictures(client, product, int(product.external_id), product.name)
        updated += 1

    logger.info("Brain sync_images done: %d products updated", updated)


# ── sync_new_products ─────────────────────────────────────────────────────────

@shared_task
def sync_new_products() -> None:
    """Import products added to Brain since the last 7 hours (runs every 6 h).

    Prevents new Brain products from waiting up to 24 h for the nightly sync.
    Uses /modified_products/new/{SID} to get only newly added product IDs,
    then fetches each via /product/{productID}/{SID} and upserts into the DB.
    """
    from django.db import transaction
    from django.utils.text import slugify as _slug

    from apps.catalog.models import Category, Product, ProductImage
    from apps.catalog.services import apply_markup
    from .client import BrainAPIClient

    client = BrainAPIClient()

    since = (datetime.utcnow() - timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
    new_ids = client.get_modified_since(since, limit=10000, mod_type="new")

    if not new_ids:
        logger.info("Brain sync_new_products: no new products since %s", since)
        return

    # Skip IDs already in our DB
    existing_ids = set(
        Product.objects.filter(
            source=Product.SOURCE_BRAIN,
            external_id__in=[str(i) for i in new_ids],
        ).values_list("external_id", flat=True)
    )
    to_import = [i for i in new_ids if str(i) not in existing_ids]

    if not to_import:
        logger.info("Brain sync_new_products: all %d new IDs already in DB", len(new_ids))
        return

    # Pre-fetch vendors for brand resolution
    vendor_map = client.get_all_vendors()

    # Pre-fetch categories for slug → local Category
    cat_slug_map: dict[str, Category] = {
        c.slug: c for c in Category.objects.filter(is_active=True)
    }

    imported = 0
    for brain_id in to_import:
        detail = client.get_product(brain_id)
        if not detail:
            continue

        name = (detail.get("name") or "").strip()
        if not name:
            continue

        # Resolve category
        brain_cat_id = detail.get("categoryID")
        local_cat: Category | None = None
        if brain_cat_id:
            # Find matching category by looking up all Brain categories
            all_cats = client.get_all_categories()
            bc = next((c for c in all_cats if c.get("categoryID") == brain_cat_id), None)
            if bc:
                cat_slug = _slug((bc.get("name") or ""), allow_unicode=True) or f"brain-cat-{brain_cat_id}"
                local_cat = cat_slug_map.get(cat_slug)

        # Brand
        brand = None
        vendor_id = detail.get("vendorID")
        if vendor_id:
            vendor_name = vendor_map.get(int(vendor_id))
            if vendor_name:
                brand = _upsert_brand(vendor_name)

        price_raw = Decimal(str(detail.get("price_uah") or detail.get("price") or 0))
        is_archive = bool(detail.get("is_archive", False))
        stock = 0 if is_archive else 1
        sku = (detail.get("articul") or detail.get("product_code") or "").strip()
        main_img = detail.get("medium_image") or detail.get("large_image") or ""

        cat_ids = [local_cat.pk] if local_cat else []
        final_price = apply_markup(price_raw, brand.pk if brand else None, cat_ids)

        slug_base = _slug(name, allow_unicode=True) or f"brain-p-{brain_id}"
        slug = _unique_slug(slug_base, brain_id, Product)

        with transaction.atomic():
            product, created = Product.objects.update_or_create(
                source=Product.SOURCE_BRAIN,
                external_id=str(brain_id),
                defaults={
                    "name": name, "slug": slug, "brand": brand,
                    "price": final_price, "purchase_price": price_raw,
                    "stock": stock, "sku": sku,
                    "is_visible": stock > 0, "image_url": main_img,
                },
            )
            if local_cat:
                product.categories.set([local_cat])
            if main_img:
                ProductImage.objects.update_or_create(
                    product=product, sort_order=0,
                    defaults={"image_url": main_img, "alt": name},
                )
            if created:
                _sync_options(client, product, brain_id)
                _sync_pictures(client, product, brain_id, name)
                imported += 1

    logger.info("Brain sync_new_products done: %d imported out of %d new IDs", imported, len(to_import))
