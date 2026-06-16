"""Cached category tree for product admin (avoids N+1 get_ancestors per category)."""

from __future__ import annotations

from django.core.cache import cache
from mptt.utils import get_cached_trees

from .models import Category

CACHE_KEY = "catalog:admin_category_tree_nodes:v1"
CACHE_TTL = 600


def invalidate_admin_category_tree_cache() -> None:
    cache.delete(CACHE_KEY)


def get_admin_category_tree_nodes() -> list[dict]:
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    qs = Category.objects.filter(is_active=True).order_by("tree_id", "lft")
    nodes: list[dict] = []

    def walk(node: Category, parts: list[str]) -> None:
        trail = [*parts, node.name]
        nodes.append(
            {
                "pk": node.pk,
                "name": node.name,
                "level": node.level,
                "path": " › ".join(trail),
            }
        )
        for child in node.get_children():
            walk(child, trail)

    for root in get_cached_trees(qs):
        walk(root, [])

    cache.set(CACHE_KEY, nodes, CACHE_TTL)
    return nodes
