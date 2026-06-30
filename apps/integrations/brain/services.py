"""Shared Brain API → catalog sync logic (single source of truth)."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils.text import slugify

if TYPE_CHECKING:
    from apps.catalog.models import Category, Product
    from apps.integrations.brain.client import BrainAPIClient

logger = logging.getLogger(__name__)

_RRP_PRICE_KEYS = ("retail_price_uah", "retail_price")


def _parse_brain_price(val) -> Decimal:
    if val is None or val == "":
        return Decimal("0")
    try:
        return Decimal(str(val).replace(",", ".")).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0")


def brain_wholesale_raw(detail: dict) -> Decimal:
    """Partner purchase price (price_uah / price)."""
    return _parse_brain_price(detail.get("price_uah") or detail.get("price"))


def brain_rrp_raw(detail: dict) -> Decimal:
    """Catalog RRP on brain.com.ua before Brain's own discount."""
    best = Decimal("0")
    for key in _RRP_PRICE_KEYS:
        parsed = _parse_brain_price(detail.get(key))
        if parsed > best:
            best = parsed
    return best


def brain_retail_price_raw(detail: dict) -> Decimal:
    """Backward-compatible alias for RRP lookup."""
    return brain_rrp_raw(detail)


def brain_customer_price(detail: dict) -> Decimal:
    """Current end-customer price on brain.com.ua — no extra markup."""
    wholesale = brain_wholesale_raw(detail)
    recommendable = _parse_brain_price(detail.get("recommendable_price"))
    rrp = brain_rrp_raw(detail)

    if recommendable > 0:
        shelf = recommendable
    elif rrp > 0:
        shelf = rrp
    elif wholesale > 0:
        shelf = wholesale
    else:
        return Decimal("0")

    # Cost floor when Brain payload is inconsistent (never sell below our purchase).
    if wholesale > 0 and shelf < wholesale:
        shelf = wholesale

    return shelf


def brain_customer_old_price(detail: dict, shelf: Decimal | None = None) -> Decimal | None:
    """Crossed-out RRP when Brain sells below catalog price (promo on brain.com.ua)."""
    if shelf is None:
        shelf = brain_customer_price(detail)
    rrp = brain_rrp_raw(detail)
    if rrp > shelf:
        return rrp
    return None


def brain_shelf_prices(detail: dict) -> tuple[Decimal, Decimal | None, Decimal]:
    """Return (shelf_price, old_price, wholesale) mirroring brain.com.ua."""
    from apps.catalog.pricing import reconcile_old_price

    wholesale = brain_wholesale_raw(detail)
    shelf = brain_customer_price(detail)
    old = reconcile_old_price(shelf, brain_customer_old_price(detail, shelf))
    return shelf, old, wholesale


def brain_sale_old_price(
    detail: dict,
    wholesale_raw: Decimal,
    brand_id: int | None,
    category_ids: list[int],
) -> Decimal | None:
    """Deprecated alias — use brain_customer_old_price."""
    _ = wholesale_raw, brand_id, category_ids
    shelf = brain_customer_price(detail)
    return brain_customer_old_price(detail, shelf)


def sync_product_options(client: "BrainAPIClient", product: "Product", brain_id: int) -> None:  # type: ignore[name-defined]
    from apps.integrations.brain.content_sync import sync_options_from_detail

    options = client.get_product_options(brain_id, lang="ua")
    if not options:
        return
    sync_options_from_detail(product, {"options": options})


def sync_product_pictures(
    client: "BrainAPIClient",
    product: "Product",
    brain_id: int,
    name: str,
) -> None:  # type: ignore[name-defined]
    from apps.catalog.gallery import is_valid_product_image_url, normalize_brain_image_url
    from apps.catalog.models import Product, ProductImage

    pics = client.get_product_pictures(brain_id)
    rows: list[tuple[int, str]] = []
    used_orders: set[int] = set()
    for i, pic in enumerate(pics):
        img_url = normalize_brain_image_url(
            pic.get("small_image") or pic.get("medium_image") or pic.get("large_image") or "",
        )
        if not img_url:
            continue
        order = int(pic.get("priority", i))
        while order in used_orders:
            order += 1
        used_orders.add(order)
        rows.append((order, img_url))

    if not rows:
        # Brain returned no usable photos — keep existing URLs/gallery (avoid wiping on API gaps).
        return

    product.images.filter(image="").delete()
    for order, url in rows:
        ProductImage.objects.update_or_create(
            product=product,
            sort_order=order,
            defaults={"image_url": url, "alt": name},
        )

    main_url = rows[0][1]
    if is_valid_product_image_url(main_url):
        Product.objects.filter(pk=product.pk).update(image_url=main_url)


def brain_hide_out_of_stock_enabled() -> bool:
    return bool(getattr(settings, "BRAIN_HIDE_OUT_OF_STOCK", True))


def _brain_is_archived(detail: dict) -> bool:
    """Parse Brain is_archive (0/1, bool, or string from JSON)."""
    val = detail.get("is_archive")
    if val is None or val == "":
        return False
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes")
    if isinstance(val, (int, float)):
        return int(val) != 0
    return bool(val)


def brain_stock_from_detail(detail: dict) -> int:
    """Brain exposes availability via is_archive (1 = archived / out of stock)."""
    return 0 if _brain_is_archived(detail) else 1


def brain_visibility(stock: int, hide_if_out_of_stock: bool) -> bool:
    if hide_if_out_of_stock and brain_hide_out_of_stock_enabled():
        return stock > 0
    return True


def brain_catalog_visible(
    *,
    stock: int,
    shelf: Decimal,
    hide_if_out_of_stock: bool,
) -> bool:
    """Hide Brain products without a retail price or when out of stock."""
    if shelf <= 0:
        return False
    return brain_visibility(stock, hide_if_out_of_stock)


def upsert_brand(name: str) -> "Brand":  # type: ignore[name-defined]
    from apps.catalog.models import Brand
    from apps.catalog.ru_localization import localize_ru_to_uk

    name = localize_ru_to_uk(name.strip())
    if not name:
        raise ValueError("brand name is empty")

    slug = slugify(name, allow_unicode=True) or f"brand-{abs(hash(name))}"
    brand = Brand.objects.filter(slug=slug).first()
    if brand:
        return brand
    brand = Brand.objects.filter(name=name).order_by("pk").first()
    if brand:
        return brand
    return Brand.objects.create(name=name, slug=slug)


def unique_product_slug(base: str, brain_id: int | str) -> str:
    from apps.catalog.models import Product

    slug = base
    counter = 1
    while (
        Product.objects.filter(slug=slug)
        .exclude(source=Product.SOURCE_BRAIN, external_id=str(brain_id))
        .exists()
    ):
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def upsert_brain_product(external_id: int | str, defaults: dict) -> tuple["Product", bool]:
    """Create or update a Brain product; merges accidental duplicates first."""
    from django.db import transaction

    from apps.catalog.models import Product
    from apps.catalog.product_dedup import dedupe_source_external_id

    ext = str(external_id)
    with transaction.atomic():
        rows = list(
            Product.objects.select_for_update()
            .filter(source=Product.SOURCE_BRAIN, external_id=ext)
            .order_by("pk")
        )
        if len(rows) > 1:
            dedupe_source_external_id(Product.SOURCE_BRAIN, ext)
            rows = list(
                Product.objects.filter(source=Product.SOURCE_BRAIN, external_id=ext).order_by("pk")
            )

        if rows:
            product = rows[0]
            for key, value in defaults.items():
                setattr(product, key, value)
            product.save()
            return product, False

        product = Product.objects.create(
            source=Product.SOURCE_BRAIN,
            external_id=ext,
            **defaults,
        )
        return product, True


def build_category_map_from_db(client: "BrainAPIClient", *, lang: str = "ua") -> dict[int, "Category"]:
    """Map Brain categoryID → existing local Category by slug (no MPTT writes)."""
    from apps.catalog.models import Category

    slug_to_cat = {c.slug: c for c in Category.objects.filter(is_active=True)}
    cat_map: dict[int, Category] = {}
    for bc in client.get_all_categories(lang=lang):
        if bc.get("realcat", 0) > 0:
            continue
        from apps.catalog.ru_localization import localize_ru_to_uk

        name = localize_ru_to_uk((bc.get("name") or "").strip())
        if not name:
            continue
        slug_base = slugify(name, allow_unicode=True) or f"brain-cat-{bc['categoryID']}"
        local = slug_to_cat.get(slug_base)
        if local:
            cat_map[int(bc["categoryID"])] = local
    return cat_map


def sync_brain_categories(client: "BrainAPIClient", *, lang: str = "ua") -> dict[int, "Category"]:
    """Import Brain category tree; return brain categoryID → local Category.

    Existing OC categories with the same slug are reused; parent moves that would
    break MPTT are skipped (InvalidMove).
    """
    from mptt.exceptions import InvalidMove

    from apps.catalog.models import Category

    all_brain_cats = client.get_all_categories(lang=lang)
    cat_map: dict[int, Category] = {}
    sorted_cats = sorted(all_brain_cats, key=lambda c: (c["parentID"], c["categoryID"]))

    for bc in sorted_cats:
        if bc.get("realcat", 0) > 0:
            continue
        cat_id = int(bc["categoryID"])
        name = (bc.get("name") or "").strip()
        if not name:
            continue
        from apps.catalog.ru_localization import localize_ru_to_uk

        name = localize_ru_to_uk(name)

        slug_base = slugify(name, allow_unicode=True) or f"brain-cat-{cat_id}"
        parent_brain_id = bc.get("parentID")
        parent_local = cat_map.get(parent_brain_id) if parent_brain_id != 1 else None

        existing = Category.objects.filter(slug=slug_base).first()
        if existing:
            cat_map[cat_id] = existing
            if existing.name != name:
                Category.objects.filter(pk=existing.pk).update(name=name)
            continue

        try:
            cat, _ = Category.objects.update_or_create(
                slug=slug_base,
                defaults={"name": name, "parent": parent_local, "is_active": True},
            )
        except InvalidMove:
            logger.warning("Brain category %s: skipped parent move for slug=%s", cat_id, slug_base)
            cat, _ = Category.objects.get_or_create(
                slug=slug_base,
                defaults={"name": name, "parent": None, "is_active": True},
            )
        cat_map[cat_id] = cat

    return cat_map


def resolve_brand(detail: dict, vendor_map: dict[int, str]) -> "Brand | None":  # type: ignore[name-defined]
    vendor_id = detail.get("vendorID")
    if not vendor_id:
        return None
    vendor_name = vendor_map.get(int(vendor_id))
    if not vendor_name:
        return None
    return upsert_brand(vendor_name)


def resolve_local_category(
    detail: dict,
    cat_map: dict[int, "Category"],
    fallback_cat_id: int | None = None,
) -> "Category | None":  # type: ignore[name-defined]
    brain_cat_id = detail.get("categoryID") or fallback_cat_id
    if not brain_cat_id:
        return None
    return cat_map.get(int(brain_cat_id))


def apply_detail_to_product(
    product: "Product",
    detail: dict,
    *,
    vendor_map: dict[int, str],
    cat_map: dict[int, "Category"],
    update_price: bool = True,
    update_stock: bool = True,
    update_brand: bool = True,
    update_category: bool = True,
    update_image: bool = False,
    force_hide_flag: bool = False,
) -> bool:
    """Apply Brain /product payload to an existing Product. Returns True if updated."""
    from apps.catalog.models import Product

    if not detail:
        return False

    from apps.catalog.ru_localization import localize_ru_to_uk

    name = localize_ru_to_uk((detail.get("name") or product.name or "").strip())
    shelf, old_price, wholesale_raw = brain_shelf_prices(detail)
    stock = brain_stock_from_detail(detail)
    sku = (detail.get("articul") or detail.get("product_code") or product.sku or "").strip()
    from apps.catalog.gallery import normalize_brain_image_url

    main_img = normalize_brain_image_url(
        detail.get("medium_image") or detail.get("large_image") or "",
    )

    brand = product.brand
    if update_brand:
        brand = resolve_brand(detail, vendor_map) or brand

    local_cat = resolve_local_category(detail, cat_map) if update_category else None
    cat_ids = (
        [local_cat.pk]
        if local_cat
        else list(product.categories.values_list("pk", flat=True))
    )
    brand_id = brand.pk if brand else None

    hide = product.hide_if_out_of_stock
    if force_hide_flag or brain_hide_out_of_stock_enabled():
        hide = True

    upd: dict = {}
    if name and name != product.name:
        from apps.catalog.content_translation import clear_en_if_uk_changed

        clear_en_if_uk_changed(product, "name", name)
        upd["name"] = name[:500]
        upd["name_en"] = None
    if update_stock:
        upd["stock"] = stock
    if sku:
        upd["sku"] = sku[:100]
    if update_brand and brand != product.brand:
        upd["brand"] = brand
    if force_hide_flag or (hide and not product.hide_if_out_of_stock):
        upd["hide_if_out_of_stock"] = True
        hide = True
    effective_stock = stock if update_stock else product.stock
    upd["is_visible"] = brain_catalog_visible(
        stock=effective_stock,
        shelf=shelf,
        hide_if_out_of_stock=hide,
    )
    if update_image and main_img:
        upd["image_url"] = main_img
    if update_price and shelf > 0:
        upd["purchase_price"] = wholesale_raw if wholesale_raw > 0 else None
        upd["price"] = shelf
        upd["old_price"] = old_price

    # Description — available only via /product/{pid} detail endpoint.
    # Write directly to _uk column to bypass modeltranslation language routing.
    raw_desc = (detail.get("description") or detail.get("description_ua") or "").strip()
    if raw_desc and raw_desc != (product.description_uk or ""):
        upd["description_uk"] = raw_desc

    if not upd:
        if local_cat and update_category:
            product.categories.set([local_cat])
        return False

    Product.objects.filter(pk=product.pk).update(**upd)
    if local_cat and update_category:
        product.categories.set([local_cat])
    return True


def upsert_product_from_detail(
    client: "BrainAPIClient",
    brain_id: int,
    detail: dict,
    *,
    vendor_map: dict[int, str],
    cat_map: dict[int, "Category"],
    sync_options: bool = False,
    sync_pictures: bool = False,
) -> tuple["Product", bool]:  # type: ignore[name-defined]
    """Create or update a Brain-sourced product from /product detail."""
    from django.db import transaction

    from apps.catalog.models import Product
    from apps.catalog.ru_localization import localize_ru_to_uk

    name = localize_ru_to_uk((detail.get("name") or "").strip())
    if not name:
        raise ValueError(f"Brain product {brain_id} has no name")

    brand = resolve_brand(detail, vendor_map)
    local_cat = resolve_local_category(detail, cat_map)
    shelf, old_price, wholesale_raw = brain_shelf_prices(detail)
    stock = brain_stock_from_detail(detail)
    sku = (detail.get("articul") or detail.get("product_code") or "").strip()
    from apps.catalog.gallery import normalize_brain_image_url

    main_img = normalize_brain_image_url(
        detail.get("medium_image") or detail.get("large_image") or "",
    )

    slug_base = slugify(name, allow_unicode=True) or f"brain-p-{brain_id}"
    slug = unique_product_slug(slug_base, brain_id)
    hide = brain_hide_out_of_stock_enabled()
    visible = brain_catalog_visible(stock=stock, shelf=shelf, hide_if_out_of_stock=hide)

    defaults = {
        "name": name[:500],
        "slug": slug,
        "brand": brand,
        "price": shelf,
        "old_price": old_price,
        "purchase_price": wholesale_raw if wholesale_raw > 0 else None,
        "stock": stock,
        "sku": sku[:100],
        "image_url": main_img,
        "hide_if_out_of_stock": hide,
        "is_visible": visible,
    }
    raw_desc = (detail.get("description") or detail.get("description_ua") or "").strip()
    if raw_desc:
        defaults["description_uk"] = raw_desc

    with transaction.atomic():
        product, created = upsert_brain_product(brain_id, defaults)
        if not created:
            apply_detail_to_product(
                product,
                detail,
                vendor_map=vendor_map,
                cat_map=cat_map,
                update_price=True,
                update_stock=True,
                update_brand=True,
                update_category=True,
                update_image=bool(main_img),
                force_hide_flag=True,
            )
            product.refresh_from_db()
        if local_cat:
            product.categories.set([local_cat])
        if sync_options:
            sync_product_options(client, product, brain_id)
        if sync_pictures:
            sync_product_pictures(client, product, brain_id, name)

    return product, created
