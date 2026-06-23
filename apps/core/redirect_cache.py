"""In-memory map of legacy redirects — avoids per-request DB lookup."""

from __future__ import annotations

from django.core.cache import cache

REDIRECT_MAP_CACHE_KEY = "core.redirect_map"
REDIRECT_CACHE_TTL = 600


def invalidate_redirect_cache() -> None:
    cache.delete(REDIRECT_MAP_CACHE_KEY)


def get_redirect_target(path: str) -> str | None:
    redirect_map = cache.get(REDIRECT_MAP_CACHE_KEY)
    if redirect_map is None:
        from apps.catalog.models import Redirect

        redirect_map = {
            row.old_path: row.new_path
            for row in Redirect.objects.filter(is_active=True).only("old_path", "new_path")
        }
        cache.set(REDIRECT_MAP_CACHE_KEY, redirect_map, REDIRECT_CACHE_TTL)
    return redirect_map.get(path)
