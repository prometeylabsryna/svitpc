"""Product gallery helpers — URL validation, deduplication, cleanup."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from django.db.models import Exists, OuterRef, Q, QuerySet

if TYPE_CHECKING:
    from apps.catalog.models import Product

# Legacy OpenCart paths (e.g. U0582287_2main.jpg) are not served on Brain CDN.
STALE_NUMBERED_MAIN_RE = re.compile(r"_\d+main\.jpg", re.IGNORECASE)
# Brain API returns these when a product has no photo; CDN responds with 404.
PLACEHOLDER_IMAGE_RE = re.compile(r"no-photo(?:-api)?\.(?:png|jpe?g|gif|webp)", re.IGNORECASE)

# Django ORM iregex patterns (keep in sync with the regexes above).
PLACEHOLDER_URL_IREGEX = r"no-photo(-api)?\.(png|jpe?g|gif|webp)"
STALE_URL_IREGEX = r"_\d+main\.jpg"


def is_stale_gallery_url(url: str) -> bool:
    if not url:
        return False
    return bool(STALE_NUMBERED_MAIN_RE.search(url))


def is_placeholder_image_url(url: str) -> bool:
    if not url:
        return False
    return bool(PLACEHOLDER_IMAGE_RE.search(url))


def is_valid_product_image_url(url: str) -> bool:
    return bool(url) and not is_stale_gallery_url(url) and not is_placeholder_image_url(url)


def _invalid_image_url_q(*, field: str = "image_url") -> Q:
    return Q(**{f"{field}__iregex": PLACEHOLDER_URL_IREGEX}) | Q(
        **{f"{field}__iregex": STALE_URL_IREGEX},
    )


def _valid_image_url_q(*, field: str = "image_url") -> Q:
    return Q(**{f"{field}__gt": ""}) & ~_invalid_image_url_q(field=field)


def _has_file_q(*, field: str = "image") -> Q:
    """Непорожній файл (ImageField): NULL і '' — обидва означають «без файлу»."""
    return Q(**{f"{field}__isnull": False}) & ~Q(**{field: ""})


def _has_display_image_q() -> Q:
    from apps.catalog.models import ProductImage

    has_valid_gallery = Exists(
        ProductImage.objects.filter(product_id=OuterRef("pk")).filter(
            _has_file_q() | _valid_image_url_q(field="image_url"),
        ),
    )
    return _has_file_q() | _valid_image_url_q(field="image_url") | has_valid_gallery


def filter_products_with_display_image(qs: QuerySet) -> QuerySet:
    """Products that resolve to a real photo (upload, valid URL, or gallery).

    Повний (дорогий) предикат з EXISTS по галереї. Для гарячих шляхів каталогу
    використовуйте денормалізований прапорець ``has_display_image`` — див.
    ``visible_catalog_products()`` та ``recompute_has_display_image()``.
    """
    return qs.filter(_has_display_image_q())


def filter_products_missing_display_image(qs: QuerySet) -> QuerySet:
    """Products with no displayable photo (placeholder/stale URLs do not count)."""
    return qs.exclude(_has_display_image_q())


def recompute_has_display_image(product_ids=None) -> int:
    """Перерахувати денормалізований Product.has_display_image.

    Два bulk UPDATE за повним предикатом. Викликати після bulk-операцій з фото
    (синки постачальників, cleanup, міграції URL), які обходять save()/сигнали.
    Повертає кількість змінених рядків.
    """
    from apps.catalog.models import Product

    qs = Product.objects.all()
    if product_ids is not None:
        qs = qs.filter(pk__in=list(product_ids))

    q = _has_display_image_q()
    changed = qs.filter(q, has_display_image=False).update(has_display_image=True)
    changed += qs.filter(~q, has_display_image=True).update(has_display_image=False)
    return changed


def normalize_brain_image_url(url: str) -> str:
    """Return URL only when Brain CDN serves a real product photo."""
    u = (url or "").strip()
    return u if is_valid_product_image_url(u) else ""


def resolve_product_image_url(product: Product) -> str:
    """Best display URL: uploaded file, then main URL, then first valid gallery image."""
    if product.image:
        return product.image.url
    if is_valid_product_image_url(product.image_url):
        return product.image_url
    for img in product.images.all():
        u = img.url
        if is_valid_product_image_url(u):
            return u
    return ""


def product_gallery_urls(product: Product) -> list[str]:
    """Unique display URLs: main first, then extra gallery images (no stale/placeholder paths)."""
    urls: list[str] = []
    seen: set[str] = set()

    candidates: list[str] = []
    if product.image:
        candidates.append(product.image.url)
    elif product.image_url:
        candidates.append(product.image_url)
    for img in product.images.all():
        candidates.append(img.url)

    for u in candidates:
        if not is_valid_product_image_url(u) or u in seen:
            continue
        seen.add(u)
        urls.append(u)

    return urls


def cleanup_product_gallery(*, dry_run: bool = False, recompute_flags: bool = True) -> dict[str, int]:
    """Remove stale OpenCart URLs, Brain placeholders, and duplicate ProductImage rows."""
    from django.db import connection

    from apps.catalog.models import Product, ProductImage

    stats = {
        "stale_deleted": 0,
        "placeholder_main_cleared": 0,
        "placeholder_gallery_deleted": 0,
        "dup_url_deleted": 0,
        "dup_sort_deleted": 0,
        "main_dup_deleted": 0,
    }

    placeholder_qs = Product.objects.filter(image_url__iregex=r"no-photo(-api)?\.(png|jpe?g|gif|webp)")
    stats["placeholder_main_cleared"] = placeholder_qs.count()
    if not dry_run and stats["placeholder_main_cleared"]:
        placeholder_qs.update(image_url="")

    placeholder_gallery_qs = ProductImage.objects.filter(image_url__iregex=r"no-photo(-api)?\.(png|jpe?g|gif|webp)")
    stats["placeholder_gallery_deleted"] = placeholder_gallery_qs.count()
    if not dry_run and stats["placeholder_gallery_deleted"]:
        placeholder_gallery_qs.delete()

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

    # recompute_flags=False лише для історичної міграції 0008 (колонки ще немає)
    if not dry_run and recompute_flags:
        stats["flag_recomputed"] = recompute_has_display_image()

    return stats
