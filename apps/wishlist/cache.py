"""Wishlist ID cache for authenticated users."""

from __future__ import annotations

from django.core.cache import cache

WISHLIST_IDS_CACHE_TTL = 300


def _wishlist_cache_key(user_id: int) -> str:
    return f"wishlist:ids:{user_id}"


def get_cached_wishlist_ids(user_id: int) -> list[int] | None:
    return cache.get(_wishlist_cache_key(user_id))


def set_cached_wishlist_ids(user_id: int, ids: list[int]) -> None:
    cache.set(_wishlist_cache_key(user_id), ids, WISHLIST_IDS_CACHE_TTL)


def invalidate_wishlist_ids_cache(user_id: int) -> None:
    cache.delete(_wishlist_cache_key(user_id))
