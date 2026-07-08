"""Лічильник переглядів товарів без UPDATE на кожен hit.

Інкременти накопичуються в Redis-hash і періодично скидаються в БД задачею
catalog.flush_product_views. Якщо Redis недоступний (develop/test на LocMem) —
фолбек на прямий атомарний UPDATE, як було раніше.
"""

from __future__ import annotations

import logging

from django.db.models import F

logger = logging.getLogger(__name__)

VIEWS_HASH_KEY = "svitpc:catalog:pending_views"


def _redis_connection():
    from django_redis import get_redis_connection

    return get_redis_connection("default")


def bump_product_view(product_id: int) -> None:
    """Зафіксувати перегляд товару (O(1), без SQL на гарячому шляху PDP)."""
    try:
        _redis_connection().hincrby(VIEWS_HASH_KEY, str(product_id), 1)
    except Exception:
        # LocMem cache / Redis недоступний — пишемо напряму (атомарно через F)
        from apps.catalog.models import Product

        Product.objects.filter(pk=product_id).update(viewed=F("viewed") + 1)


def flush_product_views() -> int:
    """Скинути накопичені перегляди в БД. Повертає кількість оновлених товарів."""
    from apps.catalog.models import Product

    try:
        conn = _redis_connection()
    except Exception:
        return 0

    pipe = conn.pipeline()
    pipe.hgetall(VIEWS_HASH_KEY)
    pipe.delete(VIEWS_HASH_KEY)
    data, _ = pipe.execute()
    if not data:
        return 0

    updated = 0
    for raw_pk, raw_count in data.items():
        try:
            pk, count = int(raw_pk), int(raw_count)
        except (TypeError, ValueError):
            continue
        if count > 0:
            updated += Product.objects.filter(pk=pk).update(viewed=F("viewed") + count)
    return updated
