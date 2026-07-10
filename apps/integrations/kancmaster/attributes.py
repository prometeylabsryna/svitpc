"""Kancmaster product characteristics → catalog ProductAttribute rows."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.catalog.models import Product

logger = logging.getLogger(__name__)

_GROUP_NAME = "Характеристики"


def sync_product_attributes(product: "Product", params: list[dict[str, str]]) -> int:
    """Upsert feed params as product attributes. Returns number of rows written."""
    from apps.catalog.derived_filters import sync_derived_filters_for_product
    from apps.catalog.models import Attribute, AttributeGroup, ProductAttribute
    from apps.catalog.ru_localization import localize_ru_to_uk

    if not params:
        return 0

    group_name = localize_ru_to_uk(_GROUP_NAME)
    group, _ = AttributeGroup.objects.get_or_create(name=group_name)
    seen_attr_ids: list[int] = []
    written = 0

    for row in params:
        attr_name = localize_ru_to_uk((row.get("name") or "").strip())
        attr_val = (row.get("value") or "").strip()
        if not attr_name or not attr_val:
            continue
        attribute, _ = Attribute.objects.get_or_create(group=group, name=attr_name)
        ProductAttribute.objects.update_or_create(
            product=product,
            attribute=attribute,
            defaults={"value": attr_val},
        )
        seen_attr_ids.append(attribute.pk)
        written += 1

    if seen_attr_ids:
        product.attributes.filter(attribute__group=group).exclude(
            attribute_id__in=seen_attr_ids
        ).delete()

    if written:
        # Сайдбар-фасети (діагональ/CPU/RAM/відеокарта/SSD/колір) — окрема таблиця ProductFilter.
        sync_derived_filters_for_product(product)

    return written
