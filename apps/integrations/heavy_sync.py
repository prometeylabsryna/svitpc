"""Mutual exclusion for RAM-heavy catalog import tasks (one at a time)."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)

LOCK_KEY = "svitpc:celery:heavy_catalog_sync"
LOCK_TTL = 4 * 3600

# Під час heavy-синку FTS-вектори не перераховуються на кожен save()
# (write amplification); pk-и накопичуються тут і зливаються батчем у finally.
PENDING_FTS_KEY = "svitpc:catalog:pending_fts_pks"
_FTS_FLUSH_BATCH = 1000


def is_heavy_sync_running() -> bool:
    from django.core.cache import cache

    return cache.get(LOCK_KEY) is not None


def defer_fts_refresh(product_id: int) -> bool:
    """Відкласти FTS-rebuild товару на кінець heavy-синку.

    True — pk записано у чергу; False — heavy-синк не йде або Redis
    недоступний (тоді викликач перераховує вектор одразу, як раніше).
    """
    if not is_heavy_sync_running():
        return False
    try:
        from django_redis import get_redis_connection

        conn = get_redis_connection("default")
        conn.sadd(PENDING_FTS_KEY, int(product_id))
        conn.expire(PENDING_FTS_KEY, LOCK_TTL)
        return True
    except Exception:
        return False


def flush_deferred_fts() -> int:
    """Перерахувати FTS-вектори для всіх відкладених товарів (батчами)."""
    try:
        from django_redis import get_redis_connection

        conn = get_redis_connection("default")
    except Exception:
        return 0

    total = 0
    while True:
        raw_pks = conn.spop(PENDING_FTS_KEY, _FTS_FLUSH_BATCH)
        if not raw_pks:
            break
        pks = [int(pk) for pk in raw_pks]

        from apps.catalog.models import Product
        from apps.catalog.search_index import refresh_product_search_vectors

        total += refresh_product_search_vectors(Product.objects.filter(pk__in=pks))
    if total:
        logger.info("Deferred FTS rebuild: %d products", total)
    return total


_ANALYZE_TABLES = ("catalog_product", "catalog_product_categories", "catalog_category")


def _analyze_catalog_tables() -> None:
    """Оновити статистику планувальника після масових UPDATE/INSERT синку.

    Без цього Postgres може обирати неефективні плани для великих категорій,
    поки autovacuum не добереться до таблиць (спостерігали TTFB 8с+ після
    міграції-бекфілу на 386k рядків).
    """
    from django.db import connection

    with connection.cursor() as cursor:
        for table in _ANALYZE_TABLES:
            cursor.execute(f"ANALYZE {table}")
    logger.info("ANALYZE done for %s", ", ".join(_ANALYZE_TABLES))


@contextmanager
def heavy_catalog_sync_lock(task_name: str) -> Iterator[bool]:
    """Return True when the lock was acquired and work should run."""
    from django.core.cache import cache

    if not cache.add(LOCK_KEY, task_name, LOCK_TTL):
        holder = cache.get(LOCK_KEY)
        logger.warning("Heavy sync %s skipped: lock held by %r", task_name, holder)
        yield False
        return

    try:
        yield True
    finally:
        if cache.get(LOCK_KEY) == task_name:
            cache.delete(LOCK_KEY)
        try:
            flush_deferred_fts()
        except Exception:
            logger.exception("Deferred FTS flush failed after %s", task_name)
        try:
            _analyze_catalog_tables()
        except Exception:
            logger.exception("ANALYZE failed after %s", task_name)
        try:
            # Синк змінив каталог — nav/home/facets не мають чекати TTL.
            # invalidate_catalog_listing_caches() сама ставить прогрів у чергу
            # (light) — окремого safe_delay(warm_listing_caches) тут не треба.
            from apps.catalog.cache_invalidation import invalidate_catalog_listing_caches

            invalidate_catalog_listing_caches()
        except Exception:
            logger.exception("Catalog cache invalidation failed after %s", task_name)
