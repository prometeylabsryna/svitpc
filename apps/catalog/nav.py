"""Navigation helpers — top-level categories with active subcategories."""

from __future__ import annotations

from django.core.cache import cache
from django.db import connection
from django.db.models import Prefetch

from .models import Category

NAV_ORDER_CACHE_KEY = "catalog:nav_order_v1"
NAV_CACHE_TIMEOUT = 600


def invalidate_nav_cache() -> None:
    cache.delete(NAV_ORDER_CACHE_KEY)


def _hidden_nav_pks() -> frozenset[int]:
    from apps.core.used_category import hidden_used_category_pks

    return hidden_used_category_pks()


def _child_qs():
    return Category.objects.filter(is_active=True).order_by("sort_order", "name")


def _base_top_qs():
    qs = Category.objects.filter(is_active=True, level=0)
    flagged = qs.filter(is_top=True).order_by("sort_order", "name")
    return flagged if flagged.exists() else qs.order_by("sort_order", "name")


def _get_subtree_product_counts(category_pks: set[int]) -> dict[int, int]:
    """One JOIN query: visible products per category subtree."""
    if not category_pks:
        return {}

    sql = """
        SELECT parent.id, COUNT(DISTINCT p.id)
        FROM catalog_category parent
        INNER JOIN catalog_category leaf
            ON leaf.tree_id = parent.tree_id
            AND leaf.lft >= parent.lft
            AND leaf.rght <= parent.rght
        INNER JOIN catalog_product_categories pc ON pc.category_id = leaf.id
        INNER JOIN catalog_product p ON p.id = pc.product_id AND p.is_visible = TRUE
        WHERE parent.id = ANY(%s)
        GROUP BY parent.id
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [list(category_pks)])
        counts = {row[0]: row[1] for row in cursor.fetchall()}

    return {pk: counts.get(pk, 0) for pk in category_pks}


def _filter_nav_categories(categories: list[Category], hidden: frozenset[int]) -> list[Category]:
    if not hidden:
        return categories
    filtered: list[Category] = []
    for cat in categories:
        if cat.pk in hidden:
            continue
        children = [child for child in cat.children.all() if child.pk not in hidden]
        cat._prefetched_objects_cache = {"children": children}
        filtered.append(cat)
    return filtered


def _sort_nav_categories(categories: list[Category], counts: dict[int, int]) -> list[Category]:
    """Categories with products first; empty ones at the bottom (keep sort_order within each group)."""
    return sorted(
        categories,
        key=lambda c: (
            0 if counts.get(c.pk, 0) > 0 else 1,
            c.sort_order,
            c.name.casefold(),
        ),
    )


def _serialize_nav_order(categories: list[Category]) -> dict:
    return {
        "tops": [c.pk for c in categories],
        "children": {
            str(c.pk): [child.pk for child in c.children.all()]
            for c in categories
        },
    }


def _load_categories_from_order(order: dict, limit: int, *, hidden: frozenset[int]) -> list[Category]:
    top_ids = [pk for pk in order["tops"] if pk not in hidden][:limit]
    child_map = order.get("children", {})
    child_ids = [cid for tid in top_ids for cid in child_map.get(str(tid), []) if cid not in hidden]
    all_ids = set(top_ids) | set(child_ids)

    by_pk = Category.objects.filter(pk__in=all_ids).in_bulk()
    categories: list[Category] = []
    for pk in top_ids:
        cat = by_pk.get(pk)
        if not cat:
            continue
        children = [by_pk[cid] for cid in child_map.get(str(pk), []) if cid in by_pk]
        cat._prefetched_objects_cache = {"children": children}
        categories.append(cat)
    return categories


def get_top_categories(limit: int = 12) -> list[Category]:
    """Top-level categories for site nav, with prefetched active children."""
    hidden = _hidden_nav_pks()
    cached_order = cache.get(NAV_ORDER_CACHE_KEY)
    if cached_order is not None:
        return _load_categories_from_order(cached_order, limit, hidden=hidden)

    categories = list(
        _base_top_qs().prefetch_related(Prefetch("children", queryset=_child_qs())),
    )
    categories = _filter_nav_categories(categories, hidden)

    nav_pks = {c.pk for c in categories}
    for cat in categories:
        nav_pks.update(child.pk for child in cat.children.all())

    counts = _get_subtree_product_counts(nav_pks)
    categories = _sort_nav_categories(categories, counts)

    order = _serialize_nav_order(categories)
    cache.set(NAV_ORDER_CACHE_KEY, order, NAV_CACHE_TIMEOUT)

    categories = categories[:limit]
    for cat in categories:
        child_ids = order["children"].get(str(cat.pk), [])
        by_pk = {c.pk: c for c in cat.children.all()}
        cat._prefetched_objects_cache = {
            "children": [by_pk[cid] for cid in child_ids if cid in by_pk],
        }

    return categories
