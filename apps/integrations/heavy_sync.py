"""Mutual exclusion for RAM-heavy catalog import tasks (one at a time)."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)

LOCK_KEY = "svitpc:celery:heavy_catalog_sync"
LOCK_TTL = 4 * 3600


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
