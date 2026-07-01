"""Kancmaster XML synchronization tasks."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from celery import shared_task
from django.db.models import Q
from django.utils.text import slugify

from apps.integrations.heavy_sync import heavy_catalog_sync_lock
from .attributes import sync_product_attributes
from .client import KancmasterXMLClient

logger = logging.getLogger(__name__)

_PROGRESS_EVERY = 2000


_PARENT_CATEGORY_SLUG = "kantseliarski-tovary"
_PARENT_CATEGORY_NAME = "Канцелярські товари"


class _SyncContext:
    """In-memory caches to avoid repeated DB lookups during full feed import."""

    def __init__(self) -> None:
        from apps.catalog.models import Brand, Category, Product

        self._Category = Category
        self._Brand = Brand
        self._parent_category: "Category | None" = self._ensure_parent_category()
        self._category_by_name: dict[str, Category] = {}
        for cat in Category.objects.only("pk", "name", "slug", "kancmaster_name", "parent_id"):
            if cat.kancmaster_name:
                self._category_by_name[cat.kancmaster_name] = cat
            self._category_by_name[cat.name] = cat
        self._brand_by_name: dict[str, Brand] = {
            b.name: b for b in Brand.objects.only("pk", "name", "slug")
        }
        self._existing_slugs: set[str] = set(
            Category.objects.values_list("slug", flat=True)
        ) | set(
            Product.objects.filter(source=Product.SOURCE_KANCMASTER).values_list("slug", flat=True)
        )
        self._product_cache: dict[str, "Product | None"] = {}  # type: ignore[name-defined]

    def _ensure_parent_category(self) -> "Category":
        """Get or create the root 'Канцелярські товари' category."""
        cat, created = self._Category.objects.get_or_create(
            slug=_PARENT_CATEGORY_SLUG,
            defaults={
                "name": _PARENT_CATEGORY_NAME,
                "is_active": True,
                "is_top": True,
                "sort_order": 50,
            },
        )
        if created:
            logger.info("Kancmaster: created parent category '%s'", _PARENT_CATEGORY_NAME)
        return cat

    def get_or_create_category(self, name: str) -> "Category | None":  # type: ignore[name-defined]
        from apps.catalog.ru_localization import localize_ru_to_uk

        raw = name.strip()
        if not raw:
            return None
        display = localize_ru_to_uk(raw)
        cached = self._category_by_name.get(raw) or self._category_by_name.get(display)
        if cached:
            if display and cached.name != display:
                cached.name = display
                cached.save(update_fields=["name", "name_en"])
            if not cached.kancmaster_name:
                cached.kancmaster_name = raw
                cached.save(update_fields=["kancmaster_name"])
            # Ensure the category is under the parent (idempotent fix for existing categories)
            if self._parent_category and cached.parent_id != self._parent_category.pk:
                cached.parent = self._parent_category
                cached.save(update_fields=["parent"])
            self._category_by_name[raw] = cached
            self._category_by_name[display] = cached
            return cached

        slug_base = slugify(display, allow_unicode=True) or f"kanc-{abs(hash(raw))}"
        slug = slug_base
        i = 1
        while slug in self._existing_slugs or self._Category.objects.filter(slug=slug).exists():
            slug = f"{slug_base}-{i}"
            i += 1

        cat = self._Category.objects.create(
            name=display,
            slug=slug,
            kancmaster_name=raw,
            parent=self._parent_category,
        )
        self._existing_slugs.add(slug)
        self._category_by_name[raw] = cat
        self._category_by_name[display] = cat
        return cat

    def get_or_create_brand(self, brand_name: str) -> "Brand | None":  # type: ignore[name-defined]
        from apps.catalog.ru_localization import localize_ru_to_uk

        brand_name = localize_ru_to_uk(brand_name.strip())
        if not brand_name:
            return None
        brand = self._brand_by_name.get(brand_name)
        if brand:
            return brand
        brand = self._Brand.objects.filter(name=brand_name).first()
        if brand:
            self._brand_by_name[brand_name] = brand
            return brand
        base_slug = slugify(brand_name, allow_unicode=True) or f"brand-{abs(hash(brand_name))}"
        slug = base_slug
        suffix = 1
        while self._Brand.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        brand = self._Brand.objects.create(name=brand_name, slug=slug)
        self._brand_by_name[brand_name] = brand
        return brand

    def unique_slug(self, name: str, ext_id: str) -> str:
        base = slugify(name, allow_unicode=True) or f"kanc-{ext_id}"
        if base not in self._existing_slugs:
            self._existing_slugs.add(base)
            return base
        slug = f"{base}-{ext_id}"
        if slug not in self._existing_slugs:
            self._existing_slugs.add(slug)
            return slug
        counter = 1
        while True:
            candidate = f"{slug}-{counter}"
            if candidate not in self._existing_slugs:
                self._existing_slugs.add(candidate)
                return candidate
            counter += 1

    def get_product(self, ext_id: str) -> "Product | None":  # type: ignore[name-defined]
        if ext_id not in self._product_cache:
            from apps.catalog.models import Product

            self._product_cache[ext_id] = Product.objects.filter(
                source=Product.SOURCE_KANCMASTER,
                external_id=ext_id,
            ).first()
        return self._product_cache[ext_id]

    def remember_product(self, prod: "Product") -> None:  # type: ignore[name-defined]
        self._product_cache[prod.external_id] = prod


def _external_gallery_qs(prod: "Product"):  # type: ignore[name-defined]
    """Gallery rows without a locally uploaded file (ImageField stored as '', not NULL)."""
    return prod.images.filter(Q(image="") | Q(image__isnull=True))


def _sync_gallery(prod: "Product", image_urls: list[str]) -> None:  # type: ignore[name-defined]
    """Sync ProductImage gallery rows for additional pictures (index 1+)."""
    from apps.catalog.models import ProductImage

    extra_urls = list(dict.fromkeys(image_urls[1:]))
    url_only = _external_gallery_qs(prod)
    if not extra_urls:
        url_only.delete()
        return

    ordered = list(url_only.order_by("sort_order"))
    current_urls = [img.image_url for img in ordered]
    current_orders = [img.sort_order for img in ordered]
    expected_orders = list(range(1, len(extra_urls) + 1))
    if current_urls == extra_urls and current_orders == expected_orders:
        return

    reserved_orders = set(
        prod.images.exclude(Q(image="") | Q(image__isnull=True)).values_list("sort_order", flat=True)
    )
    url_only.delete()

    to_create: list[ProductImage] = []
    sort_order = 1
    for url in extra_urls:
        while sort_order in reserved_orders:
            sort_order += 1
        to_create.append(ProductImage(product=prod, image_url=url, sort_order=sort_order))
        reserved_orders.add(sort_order)
        sort_order += 1

    if to_create:
        ProductImage.objects.bulk_create(to_create)


def _compute_shelf_price(
    price: Decimal,
    msrp: Decimal,
    brand_id: int | None,
    cat_ids: list[int],
) -> Decimal:
    """
    Compute the retail shelf price from Kancmaster XML feed fields.

    Priority:
    1. <msrp> (РРЦ) — use when it is greater than the purchase <price>.
       Kancmaster publishes the recommended retail price in this field.
    2. Markup rule — fallback when <msrp> is absent or not above purchase price.
       Controlled by KANCMASTER_USE_FEED_PRICE_AS_RETAIL (True = skip markup,
       False = apply MarkupRule from DB).
    """
    if msrp > price:
        return msrp

    from django.conf import settings

    from apps.catalog.pricing import enforce_retail_price
    from apps.catalog.services import apply_markup

    use_feed_as_retail: bool = getattr(settings, "KANCMASTER_USE_FEED_PRICE_AS_RETAIL", False)
    if use_feed_as_retail:
        return price

    final_price = apply_markup(price, brand_id, cat_ids)
    return enforce_retail_price(final_price, price, brand_id=brand_id, category_ids=cat_ids)


def _apply_item(ctx: _SyncContext, item: dict) -> str:
    """Upsert one feed item. Returns 'created', 'updated', or 'skipped'."""
    from django.db import transaction

    from apps.catalog.models import Product
    from apps.catalog.pricing import reconcile_old_price
    from apps.catalog.ru_localization import localize_ru_to_uk

    ext_id = (item.get("id") or "").strip()
    name = localize_ru_to_uk((item.get("name") or "").strip())
    if not ext_id or not name:
        return "skipped"

    try:
        price = Decimal(str(item.get("price") or "0").replace(",", "."))
    except InvalidOperation:
        price = Decimal("0")

    try:
        msrp = Decimal(str(item.get("msrp") or "0").replace(",", "."))
    except InvalidOperation:
        msrp = Decimal("0")

    try:
        qty = int(item.get("quantity") or 0)
    except (ValueError, TypeError):
        qty = 0

    # Save the raw description from the feed without word-by-word localization —
    # localize_ru_to_uk works well for short product names but corrupts long
    # paragraph descriptions (partial glossary match leaves a mix of languages).
    description = (item.get("description") or "").strip()
    params: list[dict[str, str]] = item.get("params") or []
    image_url = (item.get("image_url") or "").strip()
    image_urls: list[str] = item.get("image_urls") or ([image_url] if image_url else [])
    sku = (item.get("sku") or "").strip()
    brand = ctx.get_or_create_brand((item.get("brand") or "").strip())
    category = ctx.get_or_create_category((item.get("category") or "").strip())
    cat_ids = [category.pk] if category else []
    brand_id = brand.pk if brand else None
    shelf = _compute_shelf_price(price, msrp, brand_id, cat_ids)

    prod = ctx.get_product(ext_id)
    if prod is not None:
        from apps.catalog.content_translation import clear_en_if_uk_changed

        clear_en_if_uk_changed(prod, "name", name)
        prod.name = name
        prod.price = shelf
        prod.purchase_price = price
        prod.old_price = reconcile_old_price(shelf, prod.old_price)
        prod.stock = qty
        prod.is_visible = qty > 0
        if image_url:
            prod.image_url = image_url
        if description:
            clear_en_if_uk_changed(prod, "description", description)
            prod.description = description
        if sku:
            prod.sku = sku
        if brand:
            prod.brand = brand
        prod.save(
            update_fields=[
                "name",
                "price",
                "old_price",
                "purchase_price",
                "stock",
                "is_visible",
                "image_url",
                "description",
                "name_en",
                "description_en",
                "sku",
                "brand",
            ]
        )
        if category:
            prod.categories.set([category])
        _sync_gallery(prod, image_urls)
        sync_product_attributes(prod, params)
        return "updated"

    slug = ctx.unique_slug(name, ext_id)
    with transaction.atomic():
        prod = Product.objects.create(
            source=Product.SOURCE_KANCMASTER,
            external_id=ext_id,
            name=name,
            slug=slug,
            price=shelf,
            purchase_price=price,
            stock=qty,
            sku=sku,
            brand=brand,
            description=description,
            image_url=image_url,
            is_visible=qty > 0,
        )
        if category:
            prod.categories.set([category])
        _sync_gallery(prod, image_urls)
        sync_product_attributes(prod, params)
    ctx.remember_product(prod)
    return "created"


@shared_task
def sync_all() -> None:
    """Full Kancmaster XML sync: upsert all products, update descriptions/categories."""
    with heavy_catalog_sync_lock("kancmaster") as acquired:
        if not acquired:
            sync_all.apply_async(countdown=600)
            logger.warning("Kancmaster sync: lock busy, retry in 600s")
            return
        _run_kancmaster_sync()


def _run_kancmaster_sync() -> None:
    from apps.catalog.models import Product

    client = KancmasterXMLClient()
    xml_path = client.fetch_xml_path()
    if not xml_path:
        logger.warning("Kancmaster: empty XML response")
        return

    ctx = _SyncContext()
    created_count = 0
    updated_count = 0
    error_count = 0
    skipped_count = 0
    seen_ids: set[str] = set()
    total = 0

    try:
        for index, item in enumerate(client.iter_products(xml_path), start=1):
            total = index
            ext_id = (item.get("id") or "").strip()
            name = (item.get("name") or "").strip()
            if ext_id:
                seen_ids.add(ext_id)
            try:
                result = _apply_item(ctx, item)
                if result == "created":
                    created_count += 1
                elif result == "updated":
                    updated_count += 1
                else:
                    skipped_count += 1
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Kancmaster: failed to sync item id=%s name=%r: %s",
                    ext_id,
                    name,
                    exc,
                    exc_info=True,
                )
                error_count += 1

            if index % _PROGRESS_EVERY == 0:
                logger.info("Kancmaster: progress %d", index)
    finally:
        xml_path.unlink(missing_ok=True)

    logger.info("Kancmaster: %d products in feed", total)
    logger.info(
        "Kancmaster sync done: %d created, %d updated, %d skipped, %d errors",
        created_count,
        updated_count,
        skipped_count,
        error_count,
    )

    deactivated = (
        Product.objects.filter(source=Product.SOURCE_KANCMASTER, is_visible=True)
        .exclude(external_id__in=seen_ids)
        .update(is_visible=False, stock=0)
    )
    if deactivated:
        logger.info("Kancmaster: deactivated %d products removed from feed", deactivated)
