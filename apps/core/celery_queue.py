"""Safe pruning of the Celery Redis broker queue."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

CELERY_REDIS_LIST_KEY = "celery"

# Beat may enqueue the same logical job multiple times while the worker is busy.
_HEAVY_KEEP_ONE = frozenset(
    {
        "apps.integrations.kancmaster.tasks.sync_all",
        "apps.integrations.brain.tasks.sync_categories",
        "apps.integrations.brain.tasks.sync_products",
        "apps.integrations.brain.tasks.sync_brain_images_nightly",
        "apps.integrations.brain.tasks.backfill_descriptions",
        "apps.integrations.brain.tasks.sync_description_updates",
        "apps.integrations.brain.tasks.sync_options",
        "apps.integrations.brain.tasks.sync_all_availability",
        "apps.integrations.brain.tasks.sync_new_products",
        "catalog.translate_to_english",
        "apps.integrations.novaposhta.tasks.sync_np_warehouses",
        "apps.integrations.novaposhta.tasks.sync_np_cities",
    }
)

_STATUS_KEEP_ONE = frozenset(
    {
        "apps.shipping.tasks.update_delivery_statuses",
        "apps.integrations.ukrposhta.tasks.update_up_delivery_statuses",
    }
)

# Routed to the light worker — drop stale copies from the default celery list.
_LIGHT_DROP_FROM_CELERY = frozenset(
    {
        "apps.shipping.tasks.update_delivery_statuses",
        "apps.integrations.ukrposhta.tasks.update_up_delivery_statuses",
        "apps.integrations.novaposhta.tasks.sync_np_cities",
        "apps.integrations.novaposhta.tasks.sync_np_warehouses",
        "apps.integrations.novaposhta.tasks.sync_np_warehouses_chunk",
        "apps.integrations.brain.tasks.sync_prices",
        "apps.integrations.brain.tasks.sync_stock",
        "apps.integrations.brain.tasks.reconcile_stale_stock",
        "apps.integrations.brain.tasks.backfill_metadata",
        "apps.loyalty.tasks.expire_old_coins",
        "apps.loyalty.tasks.send_birthday_greetings",
    }
)

_DROP_WHEN_STALE = frozenset(
    {
        "apps.integrations.novaposhta.tasks.sync_np_warehouses_chunk",
    }
)


@dataclass(frozen=True)
class PruneStats:
    before: int
    after: int
    dropped_np_chunks: int
    dropped_light_routed: int
    dropped_duplicates: int
    dropped_other: int

    @property
    def removed(self) -> int:
        return self.before - self.after


def _task_name(raw: bytes | str) -> str:
    try:
        payload = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ""
    headers = payload.get("headers") or {}
    return str(headers.get("task") or "")


def filter_celery_messages(
    messages: list[bytes],
    *,
    drop_np_warehouse_chunks: bool = True,
    drop_light_routed: bool = True,
    dedupe_heavy: bool = True,
    dedupe_status: bool = True,
) -> tuple[list[bytes], PruneStats]:
    """Return kept broker messages (order preserved) and drop statistics."""
    kept: list[bytes] = []
    seen_heavy: set[str] = set()
    seen_status: set[str] = set()
    dropped_np = 0
    dropped_light = 0
    dropped_dup = 0
    dropped_other = 0

    for raw in messages:
        name = _task_name(raw)

        if drop_np_warehouse_chunks and name in _DROP_WHEN_STALE:
            dropped_np += 1
            continue

        if drop_light_routed and name in _LIGHT_DROP_FROM_CELERY:
            dropped_light += 1
            continue

        if dedupe_status and name in _STATUS_KEEP_ONE:
            if name in seen_status:
                dropped_dup += 1
                continue
            seen_status.add(name)

        if dedupe_heavy and name in _HEAVY_KEEP_ONE:
            if name in seen_heavy:
                dropped_dup += 1
                continue
            seen_heavy.add(name)

        kept.append(raw)

    stats = PruneStats(
        before=len(messages),
        after=len(kept),
        dropped_np_chunks=dropped_np,
        dropped_light_routed=dropped_light,
        dropped_duplicates=dropped_dup,
        dropped_other=dropped_other,
    )
    return kept, stats


def prune_celery_redis_queue(
    *,
    drop_np_warehouse_chunks: bool = True,
    drop_light_routed: bool = True,
    dedupe_heavy: bool = True,
    dedupe_status: bool = True,
    dry_run: bool = False,
) -> PruneStats:
    """Rewrite the Celery broker list on Redis DB 1. Caller should pause heavy workers."""
    from django.conf import settings

    import redis

    broker_url = settings.CELERY_BROKER_URL
    client = redis.from_url(broker_url)
    raw_messages: list[bytes] = client.lrange(CELERY_REDIS_LIST_KEY, 0, -1)
    kept, stats = filter_celery_messages(
        raw_messages,
        drop_np_warehouse_chunks=drop_np_warehouse_chunks,
        drop_light_routed=drop_light_routed,
        dedupe_heavy=dedupe_heavy,
        dedupe_status=dedupe_status,
    )

    if dry_run:
        logger.info("prune_celery_queue dry-run: %s", stats)
        return stats

    pipe = client.pipeline(transaction=True)
    pipe.delete(CELERY_REDIS_LIST_KEY)
    if kept:
        pipe.rpush(CELERY_REDIS_LIST_KEY, *kept)
    pipe.execute()
    logger.info("prune_celery_queue applied: %s", stats)
    return stats


def queue_task_counts(messages: list[bytes]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for raw in messages:
        name = _task_name(raw) or "<unknown>"
        counts[name] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def inspect_celery_redis_queue() -> dict[str, Any]:
    from django.conf import settings

    import redis

    client = redis.from_url(settings.CELERY_BROKER_URL)
    raw_messages: list[bytes] = client.lrange(CELERY_REDIS_LIST_KEY, 0, -1)
    return {
        "length": len(raw_messages),
        "tasks": queue_task_counts(raw_messages),
    }
