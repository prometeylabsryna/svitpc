"""Product gallery helpers — URL validation, deduplication, cleanup."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.catalog.models import Product

# Legacy OpenCart paths (e.g. U0582287_2main.jpg) are not served on Brain CDN.
STALE_NUMBERED_MAIN_RE = re.compile(r"_\d+main\.jpg", re.IGNORECASE)


def is_stale_gallery_url(url: str) -> bool:
    if not url:
        return False
    return bool(STALE_NUMBERED_MAIN_RE.search(url))


def product_gallery_urls(product: Product) -> list[str]:
    """Unique display URLs: main first, then extra gallery images (no stale paths)."""
    urls: list[str] = []
    seen: set[str] = set()

    main = product.main_image_url
    if main and not is_stale_gallery_url(main):
        urls.append(main)
        seen.add(main)

    for img in product.images.all():
        u = img.url
        if not u or u in seen or is_stale_gallery_url(u):
            continue
        seen.add(u)
        urls.append(u)

    return urls


def cleanup_product_gallery(*, dry_run: bool = False) -> dict[str, int]:
    """Remove stale OpenCart URLs and duplicate ProductImage rows."""
    from django.db import connection

    from apps.catalog.models import ProductImage

    stats = {"stale_deleted": 0, "dup_url_deleted": 0, "dup_sort_deleted": 0, "main_dup_deleted": 0}

    stale_qs = ProductImage.objects.filter(image_url__iregex=r"_\d+main\.jpg")
    stats["stale_deleted"] = stale_qs.count()
    if not dry_run and stats["stale_deleted"]:
        stale_qs.delete()

    no_file_a = "(a.image IS NULL OR a.image = '')"
    no_file_b = "(b.image IS NULL OR b.image = '')"
    dup_url_sql = f"""
        DELETE FROM catalog_productimage a
        USING catalog_productimage b
        WHERE a.product_id = b.product_id
          AND a.image_url = b.image_url
          AND a.image_url <> ''
          AND {no_file_a}
          AND {no_file_b}
          AND a.id > b.id
    """
    dup_sort_sql = f"""
        DELETE FROM catalog_productimage a
        USING catalog_productimage b
        WHERE a.product_id = b.product_id
          AND a.sort_order = b.sort_order
          AND {no_file_a}
          AND {no_file_b}
          AND a.id > b.id
    """
    main_dup_sql = """
        DELETE FROM catalog_productimage pi
        USING catalog_product p
        WHERE pi.product_id = p.id
          AND (pi.image IS NULL OR pi.image = '')
          AND pi.image_url <> ''
          AND p.image_url <> ''
          AND pi.image_url = p.image_url
    """

    with connection.cursor() as cursor:
        if dry_run:
            for key, sql in (
                ("dup_url_deleted", "SELECT COUNT(*) FROM catalog_productimage a INNER JOIN catalog_productimage b ON a.product_id = b.product_id AND a.image_url = b.image_url AND a.image_url <> '' AND a.image = '' AND b.image = '' AND a.id > b.id"),
                ("dup_sort_deleted", "SELECT COUNT(*) FROM catalog_productimage a INNER JOIN catalog_productimage b ON a.product_id = b.product_id AND a.sort_order = b.sort_order AND a.image = '' AND b.image = '' AND a.id > b.id"),
                ("main_dup_deleted", "SELECT COUNT(*) FROM catalog_productimage pi INNER JOIN catalog_product p ON pi.product_id = p.id WHERE pi.image = '' AND pi.image_url <> '' AND p.image_url <> '' AND pi.image_url = p.image_url"),
            ):
                cursor.execute(sql)
                stats[key] = cursor.fetchone()[0]
        else:
            for key, sql in (
                ("dup_url_deleted", dup_url_sql),
                ("dup_sort_deleted", dup_sort_sql),
                ("main_dup_deleted", main_dup_sql),
            ):
                cursor.execute(sql)
                stats[key] = cursor.rowcount

    return stats
