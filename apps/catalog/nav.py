"""Navigation helpers — top-level categories with active subcategories."""

from __future__ import annotations

from django.core.cache import cache
from django.db import connection
from django.db.models import Prefetch

from .models import Category

# v2: кешується повний payload (категорії + діти), а не лише порядок PK —
# warm path не робить жодного SQL-запиту (раніше: in_bulk на кожен запит).
NAV_ORDER_CACHE_KEY = "catalog:nav_payload_v2"
NAV_CACHE_TIMEOUT = 1800


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


def _build_nav_payload() -> list[Category]:
    """Повна побудова навігації (cache miss): запити, підрахунки, сортування.

    Hidden-фільтр тут НЕ застосовується — він накладається при читанні,
    щоб зміна прихованих категорій не вимагала перебудови payload.
    """
    categories = list(
        _base_top_qs().prefetch_related(Prefetch("children", queryset=_child_qs())),
    )

    nav_pks = {c.pk for c in categories}
    for cat in categories:
        nav_pks.update(child.pk for child in cat.children.all())

    counts = _get_subtree_product_counts(nav_pks)
    categories = _sort_nav_categories(categories, counts)
    # Підкатегорії теж: порожні — вниз (та сама політика, що для топ-рівня)
    for cat in categories:
        cat._prefetched_objects_cache = {
            "children": _sort_nav_categories(list(cat.children.all()), counts),
        }
    return categories


def get_top_categories(limit: int = 20) -> list[Category]:
    """Top-level categories for site nav, with prefetched active children.

    Warm path: 0 SQL — повністю зібрані Category-інстанси з кешу
    (cache backend повертає копії, мутувати їх безпечно).
    """
    categories: list[Category] | None = cache.get(NAV_ORDER_CACHE_KEY)
    if categories is None:
        categories = _build_nav_payload()
        cache.set(NAV_ORDER_CACHE_KEY, categories, NAV_CACHE_TIMEOUT)

    hidden = _hidden_nav_pks()
    result: list[Category] = []
    for cat in categories:
        if cat.pk in hidden:
            continue
        if hidden:
            cat._prefetched_objects_cache = {
                "children": [c for c in cat.children.all() if c.pk not in hidden],
            }
        result.append(cat)
        if len(result) >= limit:
            break
    return result
