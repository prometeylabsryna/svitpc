"""Redis cache helpers for catalog facet / count queries."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from django.core.cache import cache
from django.utils import translation

FACET_CACHE_TTL = 600
COUNT_CACHE_TTL = 300
BRAND_LIST_CACHE_TTL = 600


def catalog_filter_params(
    *,
    brand_ids: list[int],
    filter_ids: list[int],
    price_min: Decimal | None,
    price_max: Decimal | None,
    in_stock: bool,
    sort: str,
) -> dict[str, Any]:
    """Normalized filter state for cache keys (page excluded)."""
    return {
        "brand": sorted(brand_ids),
        "f": sorted(filter_ids),
        "price_min": str(price_min) if price_min is not None else "",
        "price_max": str(price_max) if price_max is not None else "",
        "in_stock": bool(in_stock),
        "sort": sort or "default",
    }


def _digest_params(params: dict[str, Any]) -> str:
    payload = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def facet_cache_key(*, scope: str, scope_id: int | str, params: dict[str, Any]) -> str:
    lang = translation.get_language() or "uk"
    return f"catalog:facets:{scope}:{scope_id}:{lang}:{_digest_params(params)}"


def count_cache_key(*, scope: str, scope_id: int | str, params: dict[str, Any]) -> str:
    lang = translation.get_language() or "uk"
    return f"catalog:count:{scope}:{scope_id}:{lang}:{_digest_params(params)}"


def brands_cache_key(*, category_id: int) -> str:
    lang = translation.get_language() or "uk"
    return f"catalog:brands:{category_id}:{lang}"


def get_cached_facets(key: str) -> dict | None:
    hit = cache.get(key)
    return hit if isinstance(hit, dict) else None


def set_cached_facets(key: str, facets: dict) -> None:
    cache.set(key, facets, FACET_CACHE_TTL)


def get_cached_count(key: str) -> int | None:
    hit = cache.get(key)
    return hit if isinstance(hit, int) else None


def set_cached_count(key: str, total: int) -> None:
    cache.set(key, total, COUNT_CACHE_TTL)


def get_cached_brand_ids(key: str) -> list[int] | None:
    hit = cache.get(key)
    if isinstance(hit, list) and all(isinstance(pk, int) for pk in hit):
        return hit
    return None


def set_cached_brand_ids(key: str, brand_ids: list[int]) -> None:
    cache.set(key, brand_ids, BRAND_LIST_CACHE_TTL)
