"""Централізована інвалідація кешів каталогу.

Кеші nav/home/facets/counts/brands живуть на TTL і не бачать масових змін
даних (синки постачальників пишуть через bulk-операції). Після завершення
синку або зміни Category кеш скидається явно, а не чекає TTL.
"""

from __future__ import annotations

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Шаблони ключів (див. facet_cache.py, home_cache.py); без KEY_PREFIX —
# django_redis.delete_pattern сам додає prefix/version.
_LISTING_CACHE_PATTERNS = (
    "catalog:facets:*",
    "catalog:count:*",
    "catalog:brands:*",
    "catalog:home:*",
)


def invalidate_home_cache() -> None:
    """Скинути блоки головної для всіх мов."""
    from django.conf import settings

    for lang, _name in settings.LANGUAGES:
        for block in ("new", "hit", "sale", "banners", "services", "bundle_v1"):
            cache.delete(f"catalog:home:{block}:{lang}")


def invalidate_catalog_listing_caches() -> None:
    """Nav + home + facets/counts/brands — після синків чи масових змін каталогу.

    На Redis використовує delete_pattern; на LocMem (dev/test) — точкові delete
    для nav/home (facets на TTL, для dev це неістотно).
    """
    from apps.catalog.nav import invalidate_nav_cache

    invalidate_nav_cache()

    if hasattr(cache, "delete_pattern"):
        for pattern in _LISTING_CACHE_PATTERNS:
            try:
                cache.delete_pattern(pattern)
            except Exception:
                logger.exception("delete_pattern failed for %s", pattern)
    else:
        invalidate_home_cache()

    logger.info("Catalog listing caches invalidated")
