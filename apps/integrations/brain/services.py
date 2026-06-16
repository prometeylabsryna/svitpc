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

_RETAIL_PRICE_KEYS = ("retail_price_uah", "recommendable_price", "retail_price")


def brain_retail_price_raw(detail: dict) -> Decimal:
    """Wholesale/RRP reference from Brain payload (before markup)."""
    for key in _RETAIL_PRICE_KEYS:
        val = detail.get(key)
        if val is None or val == "":
            continue
        try:
            parsed = Decimal(str(val).replace(",", "."))
            if parsed > 0:
                return parsed
        except Exception:
            continue
    return Decimal("0")


def brain_sale_old_price(
    detail: dict,
    wholesale_raw: Decimal,
    brand_id: int | None,
    category_ids: list[int],
) -> Decimal | None:
    """Marked-up RRP when Brain retail/recommendable price exceeds wholesale."""
    from apps.catalog.services import apply_markup

    if wholesale_raw <= 0:
        return None
    retail_raw = brain_retail_price_raw(detail)
    if retail_raw <= wholesale_raw:
        return None
    current = apply_markup(wholesale_raw, brand_id, category_ids)
    old = apply_markup(retail_raw, brand_id, category_ids)
    return old if old > current else None


def sync_product_options(client: "BrainAPIClient", product: "Product", brain_id: int) -> None:  # type: ignore[name-defined]
    from apps.catalog.models import Attribute, AttributeGroup, ProductAttribute
    from apps.catalog.ru_localization import localize_ru_to_uk

    options = client.get_product_options(brain_id, lang="ua")
    if not options:
        return

    group_name = localize_ru_to_uk("Характеристики")
    ag, _ = AttributeGroup.objects.get_or_create(name=group_name)
    for opt in options:
        attr_name = localize_ru_to_uk((opt.get("OptionName") or "").strip())
        attr_val = localize_ru_to_uk((opt.get("ValueName") or "").strip())
        if not attr_name or not attr_val:
            continue
        attr, _ = Attribute.objects.get_or_create(group=ag, name=attr_name)
        ProductAttribute.objects.update_or_create(
            product=product,
            attribute=attr,
            defaults={"value": attr_val},
        )


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
            pic.get("medium_image") or pic.get("large_image") or "",
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


def brain_stock_from_detail(detail: dict) -> int:
    """Brain exposes availability via is_archive, not warehouse qty."""
    return 0 if detail.get("is_archive") else 1


def brain_visibility(stock: int, hide_if_out_of_stock: bool) -> bool:
    if hide_if_out_of_stock and brain_hide_out_of_stock_enabled():
        return stock > 0
    return True


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
    from apps.catalog.services import apply_markup
    from apps.catalog.pricing import enforce_retail_price, reconcile_old_price

    if not detail:
        return False

    from apps.catalog.ru_localization import localize_ru_to_uk

    name = localize_ru_to_uk((detail.get("name") or product.name or "").strip())
    price_raw = Decimal(str(detail.get("price_uah") or detail.get("price") or 0))
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
    if hide and brain_hide_out_of_stock_enabled():
        upd["is_visible"] = stock > 0
    if update_image and main_img:
        upd["image_url"] = main_img
    if update_price and price_raw > 0:
        upd["purchase_price"] = price_raw
        marked = apply_markup(price_raw, brand_id, cat_ids)
        upd["price"] = enforce_retail_price(
            marked,
            price_raw,
            brand_id=brand_id,
            category_ids=cat_ids,
        )

    if price_raw > 0:
        old = brain_sale_old_price(detail, price_raw, brand_id, cat_ids)
        retail = upd.get("price", product.price)
        reconciled = reconcile_old_price(retail, old)
        if reconciled is not None:
            upd["old_price"] = reconciled
        elif "old_price" not in upd and product.old_price and product.old_price <= retail:
            upd["old_price"] = None

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
    from apps.catalog.services import apply_markup
    from apps.catalog.pricing import enforce_retail_price, reconcile_old_price
    from apps.catalog.ru_localization import localize_ru_to_uk

    name = localize_ru_to_uk((detail.get("name") or "").strip())
    if not name:
        raise ValueError(f"Brain product {brain_id} has no name")

    brand = resolve_brand(detail, vendor_map)
    local_cat = resolve_local_category(detail, cat_map)
    price_raw = Decimal(str(detail.get("price_uah") or detail.get("price") or 0))
    stock = brain_stock_from_detail(detail)
    sku = (detail.get("articul") or detail.get("product_code") or "").strip()
    from apps.catalog.gallery import normalize_brain_image_url

    main_img = normalize_brain_image_url(
        detail.get("medium_image") or detail.get("large_image") or "",
    )

    cat_ids = [local_cat.pk] if local_cat else []
    final_price = apply_markup(price_raw, brand.pk if brand else None, cat_ids) if price_raw > 0 else Decimal("0")

    slug_base = slugify(name, allow_unicode=True) or f"brain-p-{brain_id}"
    slug = unique_product_slug(slug_base, brain_id)
    hide = brain_hide_out_of_stock_enabled()
    visible = brain_visibility(stock, hide)

    brand_id = brand.pk if brand else None
    old_price = brain_sale_old_price(detail, price_raw, brand_id, cat_ids) if price_raw > 0 else None
    shelf = (
        enforce_retail_price(final_price, price_raw, brand_id=brand_id, category_ids=cat_ids)
        if price_raw > 0
        else final_price
    )

    defaults = {
        "name": name[:500],
        "slug": slug,
        "brand": brand,
        "price": shelf if shelf > 0 else price_raw,
        "old_price": reconcile_old_price(shelf, old_price),
        "purchase_price": price_raw if price_raw > 0 else None,
        "stock": stock,
        "sku": sku[:100],
        "image_url": main_img,
        "hide_if_out_of_stock": hide,
        "is_visible": visible,
    }

    with transaction.atomic():
        product, created = Product.objects.update_or_create(
            source=Product.SOURCE_BRAIN,
            external_id=str(brain_id),
            defaults=defaults,
        )
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
