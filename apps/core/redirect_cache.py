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

        # ~69k legacy OpenCart rows. `.values_list()` returns plain tuples
        # straight from the DB cursor — `.only(...)` still builds a full
        # Product... err, Redirect model instance per row (from_db + __init__
        # + post_init signal dispatch for each of the 69k rows), which alone
        # cost ~800ms on every cache-cold request (i.e. every request right
        # after a Redis restart/flush/TTL expiry — the exact "site is slow"
        # window). values_list() skips model instantiation entirely.
        redirect_map = dict(
            Redirect.objects.filter(is_active=True).values_list("old_path", "new_path")
        )
        cache.set(REDIRECT_MAP_CACHE_KEY, redirect_map, REDIRECT_CACHE_TTL)
    return redirect_map.get(path)
