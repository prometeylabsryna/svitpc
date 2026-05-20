"""Kancmaster XML synchronization tasks."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from celery import shared_task
from django.utils.text import slugify

from .client import KancmasterXMLClient

logger = logging.getLogger(__name__)


def _get_or_create_category(name: str) -> "Category | None":  # type: ignore[name-defined]
    from apps.catalog.models import Category

    if not name:
        return None
    cat = Category.objects.filter(kancmaster_name=name).first()
    if cat:
        return cat
    cat = Category.objects.filter(name=name).first()
    if cat:
        cat.kancmaster_name = name
        cat.save(update_fields=["kancmaster_name"])
        return cat
    slug_base = slugify(name, allow_unicode=True) or f"kanc-{abs(hash(name))}"
    slug = slug_base
    i = 1
    while Category.objects.filter(slug=slug).exists():
        slug = f"{slug_base}-{i}"
        i += 1
    cat = Category.objects.create(name=name, slug=slug, kancmaster_name=name)
    return cat


def _sync_gallery(prod: "Product", image_urls: list[str]) -> None:  # type: ignore[name-defined]
    """Sync ProductImage gallery rows for additional pictures (index 1+)."""
    from apps.catalog.models import ProductImage

    extra_urls = image_urls[1:]  # index 0 is already stored on Product.image_url
    if not extra_urls:
        # Remove stale gallery entries if feed no longer provides extra images
        prod.images.exclude(image__isnull=False).delete()
        return

    existing = {img.image_url: img for img in prod.images.filter(image__isnull=True)}
    incoming = set(extra_urls)

    # Remove entries no longer in feed
    for url, img in existing.items():
        if url not in incoming:
            img.delete()

    # Add new entries
    for i, url in enumerate(extra_urls):
        if url not in existing:
            prod.images.create(image_url=url, sort_order=i + 1)


@shared_task
def sync_all() -> None:
    """Full Kancmaster XML sync: upsert all products, update descriptions/categories."""
    from django.db import transaction
    from django.utils.text import slugify as _slug

    from apps.catalog.models import Brand, Product
    from apps.catalog.services import apply_markup

    client = KancmasterXMLClient()
    xml = client.fetch_xml()
    if not xml:
        logger.warning("Kancmaster: empty XML response")
        return

    items = client.parse_products(xml)
    logger.info("Kancmaster: %d products in feed", len(items))

    created_count = 0
    updated_count = 0
    error_count = 0

    for item in items:
        ext_id = (item.get("id") or "").strip()
        name = (item.get("name") or "").strip()
        if not ext_id or not name:
            continue

        try:
            try:
                price = Decimal(str(item.get("price") or "0").replace(",", "."))
            except InvalidOperation:
                price = Decimal("0")

            try:
                qty = int(item.get("quantity") or 0)
            except (ValueError, TypeError):
                qty = 0

            description = (item.get("description") or "").strip()
            image_url = (item.get("image_url") or "").strip()
            image_urls: list[str] = item.get("image_urls") or ([image_url] if image_url else [])
            sku = (item.get("sku") or "").strip()
            brand_name = (item.get("brand") or "").strip()
            cat_name = (item.get("category") or "").strip()

            brand = None
            if brand_name:
                brand_slug = _slug(brand_name, allow_unicode=True) or f"brand-{abs(hash(brand_name))}"
                brand, _ = Brand.objects.get_or_create(name=brand_name, defaults={"slug": brand_slug})

            category = _get_or_create_category(cat_name) if cat_name else None
            cat_ids = [category.pk] if category else []

            final_price = apply_markup(price, brand.pk if brand else None, cat_ids)

            try:
                prod = Product.objects.get(source=Product.SOURCE_KANCMASTER, external_id=ext_id)
                prod.name = name
                prod.price = final_price
                prod.purchase_price = price
                prod.stock = qty
                prod.is_visible = qty > 0
                if image_url:
                    prod.image_url = image_url
                if description:
                    prod.description = description
                if sku:
                    prod.sku = sku
                if brand:
                    prod.brand = brand
                prod.save(update_fields=[
                    "name", "price", "purchase_price", "stock", "is_visible",
                    "image_url", "description", "sku", "brand",
                ])
                if category:
                    prod.categories.add(category)
                _sync_gallery(prod, image_urls)
                updated_count += 1

            except Product.DoesNotExist:
                slug_base = _slug(name, allow_unicode=True) or f"kanc-{ext_id}"
                slug = slug_base
                counter = 1
                while Product.objects.filter(slug=slug).exists():
                    slug = f"{slug_base}-{counter}"
                    counter += 1
                with transaction.atomic():
                    prod = Product.objects.create(
                        source=Product.SOURCE_KANCMASTER,
                        external_id=ext_id,
                        name=name,
                        slug=slug,
                        price=final_price,
                        purchase_price=price,
                        stock=qty,
                        sku=sku,
                        brand=brand,
                        description=description,
                        image_url=image_url,
                        is_visible=qty > 0,
                    )
                    if category:
                        prod.categories.add(category)
                    _sync_gallery(prod, image_urls)
                created_count += 1

        except Exception as exc:  # noqa: BLE001
            logger.error("Kancmaster: failed to sync item id=%s name=%r: %s", ext_id, name, exc, exc_info=True)
            error_count += 1

    logger.info(
        "Kancmaster sync done: %d created, %d updated, %d errors",
        created_count, updated_count, error_count,
    )

    # Deactivate products that are no longer present in the feed
    seen_ids = {(item.get("id") or "").strip() for item in items if (item.get("id") or "").strip()}
    deactivated = (
        Product.objects
        .filter(source=Product.SOURCE_KANCMASTER, is_visible=True)
        .exclude(external_id__in=seen_ids)
        .update(is_visible=False, stock=0)
    )
    if deactivated:
        logger.info("Kancmaster: deactivated %d products removed from feed", deactivated)
