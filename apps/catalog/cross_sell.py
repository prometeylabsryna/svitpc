"""Cross-sell suggestions: accessories for laptops/PCs instead of same-type products."""

from __future__ import annotations

from django.core.cache import cache
from django.db.models import Avg, Count, Q, QuerySet

from apps.promotions.services import with_active_promotions

from .models import Category, Product
from .services import order_stock_first, visible_catalog_products

_SUGGESTED_LIMIT = 6
_SUBTREE_CACHE_TTL = 3600

_LAPTOP_ROOT = "ноутбуки-планшети"
_PC_ROOT = "компютери-аксесуари"

_LAPTOP_PRIMARY_SLUGS = frozenset({"ноутбуки", "планшети", "електронні-книги"})
_PC_PRIMARY_SLUGS = frozenset({"компютери", "монітори"})

# Department landing pages list only primary devices in the main grid.
_LAPTOP_DEPT_LISTING_SLUGS = ("ноутбуки", "планшети", "електронні-книги")
_PC_DEPT_LISTING_SLUGS = ("компютери",)

_LAPTOP_ACCESSORY_TARGETS = (
    "аксесуари-для-ноутбуків",
    "сумки-рюкзаки-чохли",
    "аксесуари-для-планшетів",
    "маніпулятори",
)
_PC_ACCESSORY_TARGETS = (
    "монітори-та-аксесуари",
    "маніпулятори",
    "кабелі-та-перехідники-1462",
    "килимки-та-серветки",
)
_MONITOR_ACCESSORY_TARGETS = (
    "аксесуари-для-моніторів",
    "кабелі-та-перехідники-1462",
)

_ACCESSORY_MARKERS = (
    "аксесуар",
    "сумк",
    "рюкзак",
    "чохл",
    "підставк",
    "док-стан",
    "комплектуюч",
    "запчастин",
    "маніпулятор",
    "мишк",
    "клавіатур",
    "кабел",
    "килимок",
    "монітор-та-аксесуар",
)


def _subtree_pks(slug: str) -> list[int]:
    cache_key = f"catalog:subtree_pks:{slug}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        root = Category.objects.only("pk", "tree_id", "lft", "rght").get(slug=slug, is_active=True)
    except Category.DoesNotExist:
        return []
    pks = list(
        Category.objects.filter(
            tree_id=root.tree_id,
            lft__gte=root.lft,
            rght__lte=root.rght,
            is_active=True,
        ).values_list("pk", flat=True)
    )
    cache.set(cache_key, pks, _SUBTREE_CACHE_TTL)
    return pks


def _union_subtree_pks(slugs: tuple[str, ...]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for slug in slugs:
        for pk in _subtree_pks(slug):
            if pk not in seen:
                seen.add(pk)
                out.append(pk)
    return out


def _ancestor_slugs(category: Category) -> frozenset[str]:
    return frozenset(a.slug for a in category.get_ancestors(include_self=True))


def _is_accessory_category(category: Category) -> bool:
    haystack = f"{category.slug} {category.name}".lower()
    return any(marker in haystack for marker in _ACCESSORY_MARKERS)


def _product_branch(categories: list[Category]) -> str | None:
    for category in categories:
        slugs = _ancestor_slugs(category)
        if _LAPTOP_ROOT in slugs:
            return "laptop"
        if _PC_ROOT in slugs:
            return "pc"
    return None


def _product_is_primary_device(categories: list[Category], branch: str) -> bool:
    primary = _LAPTOP_PRIMARY_SLUGS if branch == "laptop" else _PC_PRIMARY_SLUGS
    for category in categories:
        if category.slug in primary:
            return True
    return False


def _product_is_accessory(categories: list[Category]) -> bool:
    return any(_is_accessory_category(category) for category in categories)


def primary_listing_category_pks(category: Category) -> list[int] | None:
    """Category PKs for the main product grid on department landing pages."""
    if category.slug == _LAPTOP_ROOT:
        return _union_subtree_pks(_LAPTOP_DEPT_LISTING_SLUGS)
    if category.slug == _PC_ROOT:
        return _union_subtree_pks(_PC_DEPT_LISTING_SLUGS)
    return None


def _cross_sell_target_slugs_for_product(categories: list[Category]) -> tuple[str, ...] | None:
    branch = _product_branch(categories)
    if not branch:
        return None
    if _product_is_accessory(categories):
        return None
    if not _product_is_primary_device(categories, branch):
        return None

    if branch == "laptop":
        targets = list(_LAPTOP_ACCESSORY_TARGETS)
        if not any(category.slug == "планшети" for category in categories):
            targets = [slug for slug in targets if slug != "аксесуари-для-планшетів"]
        return tuple(targets)

    if any(category.slug == "монітори" for category in categories):
        return _MONITOR_ACCESSORY_TARGETS
    return _PC_ACCESSORY_TARGETS


def _cross_sell_target_slugs_for_category(category: Category) -> tuple[str, ...] | None:
    if category.slug == _LAPTOP_ROOT:
        return tuple(slug for slug in _LAPTOP_ACCESSORY_TARGETS if slug != "аксесуари-для-планшетів")

    if category.slug == _PC_ROOT:
        return _PC_ACCESSORY_TARGETS

    slugs = _ancestor_slugs(category)
    if _LAPTOP_ROOT in slugs:
        if _is_accessory_category(category) or category.slug in {"запчастини-для-ноутбуків", "комплектуючі-до-ноутбуків"}:
            return None
        if category.slug in _LAPTOP_PRIMARY_SLUGS:
            targets = list(_LAPTOP_ACCESSORY_TARGETS)
            if category.slug != "планшети":
                targets = [slug for slug in targets if slug != "аксесуари-для-планшетів"]
            return tuple(targets)
        return None

    if _PC_ROOT in slugs:
        if _is_accessory_category(category):
            return None
        if category.slug in _PC_PRIMARY_SLUGS:
            if category.slug == "монітори":
                return _MONITOR_ACCESSORY_TARGETS
            return _PC_ACCESSORY_TARGETS
    return None


def _annotate_reviews(qs: QuerySet[Product]) -> QuerySet[Product]:
    approved = Q(reviews__is_approved=True)
    return qs.annotate(
        avg_rating_ann=Avg("reviews__rating", filter=approved),
        review_count_ann=Count("reviews", filter=approved),
    )


def _pick_products(
    category_pks: list[int],
    *,
    exclude_pk: int | None = None,
    limit: int = _SUGGESTED_LIMIT,
) -> list[Product]:
    if not category_pks:
        return []
    qs = visible_catalog_products().filter(categories__in=category_pks)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    qs = (
        with_active_promotions(_annotate_reviews(qs))
        .select_related("brand")
        .prefetch_related("images")
        .distinct()
    )
    qs = order_stock_first(qs, "-viewed", "sort_order")
    return list(qs[:limit])


def _same_category_products(product: Product, *, limit: int = _SUGGESTED_LIMIT) -> list[Product]:
    category_pks = [category.pk for category in product.categories.all()]
    if not category_pks:
        return []
    return _pick_products(category_pks, exclude_pk=product.pk, limit=limit)


def suggested_products_for_product(product: Product, *, limit: int = _SUGGESTED_LIMIT) -> tuple[list[Product], bool]:
    """Return (products, is_cross_sell). Falls back to same-category when needed."""
    categories = list(product.categories.all())
    target_slugs = _cross_sell_target_slugs_for_product(categories)
    if target_slugs:
        picked = _pick_products(_union_subtree_pks(target_slugs), exclude_pk=product.pk, limit=limit)
        if picked:
            return picked, True
    return _same_category_products(product, limit=limit), False


def suggested_products_for_category(category: Category, *, limit: int = _SUGGESTED_LIMIT) -> tuple[list[Product], bool]:
    """Accessory block for category listing pages (page 1 only in the view)."""
    target_slugs = _cross_sell_target_slugs_for_category(category)
    if not target_slugs:
        return [], False
    picked = _pick_products(_union_subtree_pks(target_slugs), limit=limit)
    return picked, bool(picked)
