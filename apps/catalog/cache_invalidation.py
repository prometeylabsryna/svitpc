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


def invalidate_catalog_listing_caches(*, rewarm: bool = True) -> None:
    """Nav + home + facets/counts/brands — після синків чи масових змін каталогу.

    На Redis використовує delete_pattern; на LocMem (dev/test) — точкові delete
    для nav/home (facets на TTL, для dev це неістотно).

    За замовчуванням одразу ставить у чергу (light) прогрів COUNT/фасетів/брендів
    для топ-категорій — щоб реальний відвідувач ніколи не платив за холодний
    кеш, і сайт не залежав від того, чи хтось не забув запустити прогрів
    вручну після адмінської дії/бекфілу. `rewarm=False` — коли викликач сам
    прогріває інакше (напр. одразу після) і друге постановлення в чергу зайве.
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

    if rewarm:
        _schedule_rewarm()


def _schedule_rewarm() -> None:
    from apps.catalog.tasks import warm_listing_caches
    from apps.core.celery_utils import safe_delay

    if safe_delay(warm_listing_caches):
        logger.info("Catalog listing caches: rewarm scheduled (light queue)")
    else:
        logger.warning(
            "Catalog listing caches: rewarm NOT scheduled (broker unavailable) — "
            "next visitor to a large category pays cold COUNT/facets until Beat's 15-min tick",
        )
