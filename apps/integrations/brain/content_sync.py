"""Brain products/content API — full descriptions, options, images (OWN_MODE)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.catalog.models import Product
    from apps.integrations.brain.client import BrainAPIClient

logger = logging.getLogger(__name__)


def brain_description_text(detail: dict) -> str:
    """Extract Ukrainian product description from /product or /products/content payload."""
    desc = (detail.get("description") or detail.get("description_ua") or "").strip()
    if desc:
        return desc
    return (detail.get("brief_description") or "").strip()


def sync_options_from_detail(product: "Product", detail: dict) -> int:
    """Apply characteristics from content payload (options array). Returns count written."""
    from apps.catalog.models import Attribute, AttributeGroup, ProductAttribute
    from apps.catalog.ru_localization import localize_ru_to_uk

    options = detail.get("options") or []
    if not options:
        return 0

    group_name = localize_ru_to_uk("Характеристики")
    ag, _ = AttributeGroup.objects.get_or_create(name=group_name)
    written = 0
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
        written += 1
    return written


def sync_pictures_from_detail(product: "Product", detail: dict, name: str) -> bool:
    """Apply gallery images from content payload when present."""
    from apps.catalog.gallery import is_valid_product_image_url, normalize_brain_image_url
    from apps.catalog.models import Product, ProductImage

    pics = detail.get("images") or []
    if not pics:
        return False

    rows: list[tuple[int, str]] = []
    used_orders: set[int] = set()
    for i, pic in enumerate(pics):
        img_url = normalize_brain_image_url(
            pic.get("medium_image") or pic.get("large_image") or pic.get("full_image") or "",
        )
        if not img_url:
            continue
        order = int(pic.get("priority", i))
        while order in used_orders:
            order += 1
        used_orders.add(order)
        rows.append((order, img_url))

    if not rows:
        return False

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
    return True


def apply_brain_content_item(
    product: "Product",
    item: dict,
    *,
    sync_options: bool = True,
    sync_images: bool = False,
) -> bool:
    """Apply description (+ optional options/images) from products/content list item."""
    from apps.catalog.models import Product

    changed = False
    raw_desc = brain_description_text(item)
    if raw_desc and raw_desc != (product.description_uk or ""):
        from apps.catalog.content_translation import clear_en_if_uk_changed

        clear_en_if_uk_changed(product, "description", raw_desc)
        Product.objects.filter(pk=product.pk).update(description_uk=raw_desc)
        product.description_uk = raw_desc
        changed = True

    if sync_options and sync_options_from_detail(product, item):
        changed = True

    if sync_images and sync_pictures_from_detail(product, item, product.name):
        changed = True

    return changed


def backfill_descriptions_from_content(
    client: "BrainAPIClient",
    products_by_brain_id: dict[int, "Product"],
    *,
    skip_options: bool = False,
    sync_images: bool = False,
) -> tuple[int, int, int]:
    """Fetch products/content in batches and apply to local products.

    Returns (updated_count, no_description_count, api_miss_count).
    """
    if not products_by_brain_id:
        return 0, 0, 0

    brain_ids = list(products_by_brain_id.keys())
    try:
        content_items = client.get_products_content(brain_ids)
    except Exception:
        logger.exception("Brain get_products_content failed for %d ids", len(brain_ids))
        return 0, 0, len(brain_ids)

    returned_ids: set[int] = set()
    updated = 0
    no_desc = 0

    for item in content_items:
        try:
            brain_id = int(item.get("productID") or 0)
        except (TypeError, ValueError):
            continue
        if brain_id <= 0:
            continue
        returned_ids.add(brain_id)
        product = products_by_brain_id.get(brain_id)
        if product is None:
            continue
        if not brain_description_text(item):
            no_desc += 1
            if not skip_options and item.get("options"):
                if sync_options_from_detail(product, item):
                    updated += 1
            continue
        if apply_brain_content_item(
            product,
            item,
            sync_options=not skip_options,
            sync_images=sync_images,
        ):
            updated += 1

    api_miss = len(brain_ids) - len(returned_ids)

    if api_miss > 0:
        updated += _fallback_descriptions_via_product_endpoint(
            client,
            products_by_brain_id,
            returned_ids,
            skip_options=skip_options,
        )

    if not skip_options:
        updated += _fallback_options_via_product_endpoint(client, products_by_brain_id)

    return updated, no_desc, api_miss


def _fallback_options_via_product_endpoint(
    client: "BrainAPIClient",
    products_by_brain_id: dict[int, "Product"],
    *,
    max_calls: int = 50,
) -> int:
    """Pull /product_options when batch content had no warranty row (idempotent update_or_create)."""
    from apps.integrations.brain.services import sync_product_options

    extra = 0
    pending: list[tuple[int, Product]] = []
    for brain_id, product in products_by_brain_id.items():
        if product.attributes.filter(attribute__name__icontains="Гарант").exists():
            continue
        pending.append((brain_id, product))

    for brain_id, product in pending[:max_calls]:
        try:
            sync_product_options(client, product, brain_id)
        except Exception:
            logger.exception("Brain sync_product_options fallback failed for %s", brain_id)
            continue
        if product.attributes.filter(attribute__name__icontains="Гарант").exists():
            extra += 1
    return extra


def _fallback_descriptions_via_product_endpoint(
    client: "BrainAPIClient",
    products_by_brain_id: dict[int, "Product"],
    returned_ids: set[int],
    *,
    skip_options: bool,
    max_calls: int = 25,
) -> int:
    """Single-product /product/{id} fallback when batch content API omits rows."""
    extra = 0
    misses = [bid for bid in products_by_brain_id if bid not in returned_ids]
    for brain_id in misses[:max_calls]:
        product = products_by_brain_id.get(brain_id)
        if product is None:
            continue
        try:
            detail = client.get_product(brain_id)
        except Exception:
            logger.exception("Brain get_product fallback failed for %s", brain_id)
            continue
        if not detail:
            continue
        if apply_brain_content_item(
            product,
            detail,
            sync_options=not skip_options,
            sync_images=False,
        ):
            extra += 1
            continue
        if not skip_options and not product.attributes.filter(attribute__name__icontains="Гарант").exists():
            from apps.integrations.brain.services import sync_product_options

            try:
                sync_product_options(client, product, brain_id)
            except Exception:
                logger.exception("Brain get_product options fallback failed for %s", brain_id)
                continue
            if product.attributes.filter(attribute__name__icontains="Гарант").exists():
                extra += 1
    return extra
