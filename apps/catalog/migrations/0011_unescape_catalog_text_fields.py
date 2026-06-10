"""Decode HTML entities in product/brand names from legacy OpenCart import."""

import html

from django.db import migrations
from django.db.models import Q

_BATCH = 2000

_PRODUCT_FIELDS = (
    "name",
    "name_uk",
    "name_en",
    "short_description",
    "short_description_uk",
    "short_description_en",
    "seo_title",
    "seo_title_uk",
    "seo_title_en",
    "seo_description",
    "seo_description_uk",
    "seo_description_en",
)

_BRAND_FIELDS = ("name", "name_uk", "name_en")


def _unescape_fields(instances: list, fields: tuple[str, ...]) -> list:
    changed: list = []
    for obj in instances:
        dirty = False
        for field in fields:
            raw = getattr(obj, field, None)
            if not raw or "&" not in raw:
                continue
            decoded = html.unescape(raw)
            if decoded != raw:
                setattr(obj, field, decoded)
                dirty = True
        if dirty:
            changed.append(obj)
    return changed


def _bulk_unescape(model, fields: tuple[str, ...]) -> int:
    cond = Q()
    for field in fields:
        cond |= Q(**{f"{field}__contains": "&"})
    qs = model.objects.filter(cond).order_by("pk")
    total_updated = 0
    last_pk = 0
    while True:
        chunk = list(qs.filter(pk__gt=last_pk)[:_BATCH])
        if not chunk:
            break
        changed = _unescape_fields(chunk, fields)
        if changed:
            model.objects.bulk_update(changed, fields)
            total_updated += len(changed)
        last_pk = chunk[-1].pk
    return total_updated


def unescape_catalog_text(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    Brand = apps.get_model("catalog", "Brand")
    _bulk_unescape(Product, _PRODUCT_FIELDS)
    _bulk_unescape(Brand, _BRAND_FIELDS)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0010_product_search_vector"),
    ]

    operations = [
        migrations.RunPython(unescape_catalog_text, noop),
    ]
