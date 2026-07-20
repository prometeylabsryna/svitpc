"""Catalog business logic — filtering, sorting, search helpers."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import (
    Avg,
    Case,
    Count,
    Exists,
    F,
    FloatField,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core.i18n import localized_field

from .models import Category, Filter, Product


def visible_catalog_products() -> QuerySet[Product]:
    """Visible products with a real display photo (no placeholder/stale URLs).

    Фото перевіряється денормалізованим прапорцем has_display_image
    (індекс is_visible+has_display_image) замість EXISTS по галереї.
    """
    return Product.objects.filter(is_visible=True, has_display_image=True).filter(
        Q(stock__gt=0) | Q(hide_if_out_of_stock=False),
    )


def category_listing_products(category: Category) -> QuerySet[Product]:
    """Products for a category page — subtree plus items assigned to ancestor categories only.

    Uses an EXISTS semi-join against the M2M through table instead of a
    JOIN + DISTINCT: a product can be linked to several categories inside
    the same subtree, so the JOIN form duplicates rows and forces Postgres
    to deduplicate tens of thousands of rows on every COUNT/listing query
    for large subtrees (e.g. the ~57k-product "Канцелярські товари" tree).
    EXISTS never duplicates rows, so no DISTINCT is needed at all.
    """
    from .cross_sell import primary_listing_category_pks

    primary_pks = primary_listing_category_pks(category)
    if primary_pks is not None:
        return visible_catalog_products().filter(categories__in=primary_pks).distinct()

    subtree_pks = Category.objects.filter(tree_id=category.tree_id).filter(
        Q(lft__gte=category.lft, rght__lte=category.rght)
        | Q(lft__lt=category.lft, rght__gt=category.rght)
    ).values("pk")

    through = Product.categories.through
    membership = through.objects.filter(
        product_id=OuterRef("pk"),
        category_id__in=Subquery(subtree_pks),
    )
    return visible_catalog_products().filter(Exists(membership))


def category_listing_category_scope(category: Category) -> QuerySet[Category]:
    """Category nodes used for brand facets on a category listing page."""
    from .cross_sell import primary_listing_category_pks

    primary_pks = primary_listing_category_pks(category)
    if primary_pks is not None:
        return Category.objects.filter(pk__in=primary_pks, is_active=True)

    return Category.objects.filter(tree_id=category.tree_id).filter(
        Q(lft__gte=category.lft, rght__lte=category.rght)
        | Q(lft__lt=category.lft, rght__gt=category.rght)
    )


def order_stock_first(qs: QuerySet[Product], *order_fields: str) -> QuerySet[Product]:
    """Annotate and order queryset so in-stock products appear before out-of-stock ones."""
    return qs.annotate(
        in_stock_order=Case(
            When(stock__gt=0, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by("in_stock_order", *order_fields)


def expand_equivalent_filter_ids(filter_ids: list[int]) -> list[int]:
    """Expand selected Filter PKs to all duplicates with the same group+name.

    OpenCart import left duplicate ``Filter`` rows (same group/name, different pk).
    Facets collapse them to one checkbox (highest count), so shoppers click one
    ID while products remain linked to a sibling — without expansion the OR/AND
    chain silently drops those products.
    """
    if not filter_ids:
        return []
    from .models import Filter as FilterModel

    rows = list(FilterModel.objects.filter(id__in=filter_ids).values("group_id", "name"))
    if not rows:
        return list(filter_ids)
    q = Q()
    for row in rows:
        q |= Q(group_id=row["group_id"], name=row["name"])
    return list(FilterModel.objects.filter(q).values_list("id", flat=True).distinct())


def get_filtered_products(
    queryset: QuerySet[Product],
    brands: list[int] | None = None,
    filters: list[int] | None = None,
    price_min: Decimal | None = None,
    price_max: Decimal | None = None,
    in_stock_only: bool = False,
    sort: str = "default",
    *,
    with_reviews_ann: bool = True,
    for_count: bool = False,
    skip_image_filter: bool = False,
) -> QuerySet[Product]:
    """Apply catalog filters and sorting to a product queryset."""

    qs = queryset.filter(is_visible=True)
    if not skip_image_filter:
        qs = qs.filter(has_display_image=True)

    if brands:
        qs = qs.filter(brand_id__in=brands)
    if filters:
        # OR within a group, AND between groups:
        # group selected filter IDs by their FilterGroup, then chain one
        # .filter(filters__filter_id__in=[...]) per group so products only
        # need to match *any* value inside a group but *all* selected groups.
        from .models import Filter as FilterModel

        expanded = expand_equivalent_filter_ids(list(filters))
        group_map: dict[int, list[int]] = {}
        for row in FilterModel.objects.filter(id__in=expanded).values("id", "group_id"):
            group_map.setdefault(row["group_id"], []).append(row["id"])
        for group_filter_ids in group_map.values():
            qs = qs.filter(filters__filter_id__in=group_filter_ids).distinct()
    if price_min is not None:
        qs = qs.filter(price__gte=price_min)
    if price_max is not None:
        qs = qs.filter(price__lte=price_max)
    if in_stock_only:
        qs = qs.filter(stock__gt=0)

    if for_count:
        return qs

    return finalize_product_listing(qs, sort, with_reviews_ann=with_reviews_ann)


LISTING_SORT_MAP = {
    "price_asc": "price",
    "price_desc": "-price",
    "new": "-date_added",
    "name_asc": "name",
    "name_desc": "-name",
    "popular": "-viewed",
    "rating": "-avg_rating_ann",
    "default": "sort_order",
}


def finalize_product_listing(
    qs: QuerySet[Product],
    sort: str = "default",
    *,
    with_reviews_ann: bool = True,
) -> QuerySet[Product]:
    """Довести відфільтрований queryset до готового для рендеру:
    annotate відгуків, сортування, select_related/prefetch.

    Дозволяє будувати фільтри ОДИН раз (для count/фасетів) і доводити
    той самий queryset для сторінки — без другої побудови з нуля.
    """
    sort_field = LISTING_SORT_MAP.get(sort, "sort_order")

    if with_reviews_ann:
        # Annotate so product cards avoid N+1 queries when rendering
        # avg_rating / review_count (@property reads these via __dict__ first).
        #
        # Correlated Subquery instead of a JOIN+Avg/Count(GROUP BY): the JOIN
        # form forces Postgres to aggregate every matching row (tens of
        # thousands for large categories) before it can ORDER BY + LIMIT.
        # A scalar subquery lets the planner sort/limit the base queryset
        # first and only evaluate the review stats for the winning page of
        # rows — the listing itself only ever needs `sort` (rating-sort is
        # the one case where the DB must still touch every row's subquery).
        from apps.reviews.models import Review

        approved = Review.objects.filter(product_id=OuterRef("pk"), is_approved=True)
        review_avg_sq = approved.order_by().values("product_id").annotate(a=Avg("rating")).values("a")
        review_count_sq = approved.order_by().values("product_id").annotate(c=Count("id")).values("c")
        qs = qs.annotate(
            avg_rating_ann=Subquery(review_avg_sq, output_field=FloatField()),
            review_count_ann=Coalesce(
                Subquery(review_count_sq, output_field=IntegerField()), Value(0)
            ),
        )

    qs = order_stock_first(qs, sort_field)

    return qs.select_related("brand").prefetch_related("images")


def _compute_product_facets(
    product_ids: QuerySet[Product],
    *,
    only_group_id: int | None = None,
) -> dict:
    """Build facet groups for products matching ``product_ids`` (subquery-safe).

    Duplicate Filter rows (same group+name) are merged: counts are summed and
    the canonical checkbox id is the smallest pk (stable, matches derived_filters).
    """
    qs = Filter.objects.filter(
        productfilter__product_id__in=product_ids.values("pk"),
        group__is_brand=False,
    )
    if only_group_id is not None:
        qs = qs.filter(group_id=only_group_id)
    filter_groups = (
        qs.select_related("group")
        .annotate(count=Count("productfilter__product", distinct=True))
        .order_by("group__sort_order", "group__name_uk", "name_uk", "pk")
    )

    by_name: dict[str, dict] = {}
    for f in filter_groups:
        gname = localized_field(f.group, "name")
        if gname not in by_name:
            by_name[gname] = {"name": gname, "gid": f.group_id, "options": {}}
        opts = by_name[gname]["options"]
        opt_name = localized_field(f, "name")
        if opt_name not in opts:
            opts[opt_name] = {"id": f.id, "name": opt_name, "count": f.count}
        else:
            # Keep smallest pk as canonical id; sum counts across duplicates.
            if f.id < opts[opt_name]["id"]:
                opts[opt_name]["id"] = f.id
            opts[opt_name]["count"] += f.count

    facets: dict[int, dict] = {}
    for gdata in by_name.values():
        gid = gdata["gid"]
        facets[gid] = {
            "name": gdata["name"],
            "options": sorted(gdata["options"].values(), key=lambda o: o["name"]),
        }

    return facets


def get_product_facets(
    current_qs: QuerySet[Product],
    *,
    cache_key: str | None = None,
) -> dict:
    """Return filter group options with product counts for any product queryset."""
    from .facet_cache import get_cached_facets, set_cached_facets

    if cache_key:
        cached = get_cached_facets(cache_key)
        if cached is not None:
            return cached

    facets = _compute_product_facets(current_qs)

    if cache_key:
        set_cached_facets(cache_key, facets)

    return facets


def get_disjunctive_facets(
    base_qs: QuerySet[Product],
    *,
    brand_ids: list[int] | None = None,
    filter_ids: list[int] | None = None,
    price_min: Decimal | None = None,
    price_max: Decimal | None = None,
    in_stock: bool = False,
    cache_key: str | None = None,
) -> dict:
    """Facet counts with OR-within-group semantics (standard faceted search).

    Counts for group G ignore selected filters that belong to G, so choosing
    «Чорний» still shows «Білий» with a count (multi-select OR). Brand / price /
    stock and *other* groups stay applied.
    """
    from .facet_cache import get_cached_facets, set_cached_facets
    from .models import Filter as FilterModel

    if cache_key:
        cached = get_cached_facets(cache_key)
        if cached is not None:
            return cached

    selected = list(filter_ids or [])
    by_group: dict[int, list[int]] = {}
    if selected:
        for row in FilterModel.objects.filter(id__in=selected).values("id", "group_id"):
            by_group.setdefault(row["group_id"], []).append(row["id"])

    qs_base = get_filtered_products(
        base_qs,
        brands=brand_ids,
        filters=None,
        price_min=price_min,
        price_max=price_max,
        in_stock_only=in_stock,
        for_count=True,
        skip_image_filter=True,
    )
    group_ids = list(
        Filter.objects.filter(
            productfilter__product_id__in=qs_base.values("pk"),
            group__is_brand=False,
        )
        .values_list("group_id", flat=True)
        .distinct(),
    )

    facets: dict[int, dict] = {}
    for gid in group_ids:
        other_ids = [
            fid for other_gid, ids in by_group.items() if other_gid != gid for fid in ids
        ]
        qs_g = get_filtered_products(
            base_qs,
            brands=brand_ids,
            filters=other_ids or None,
            price_min=price_min,
            price_max=price_max,
            in_stock_only=in_stock,
            for_count=True,
            skip_image_filter=True,
        )
        partial = _compute_product_facets(qs_g, only_group_id=gid)
        facets.update(partial)

    if cache_key:
        set_cached_facets(cache_key, facets)

    return facets


def annotate_facet_active_state(facets: dict, filter_ids: list[int]) -> dict:
    """Mark groups that have a selected option (for expand/collapse UI)."""
    selected = set(filter_ids or [])
    for gdata in facets.values():
        gdata["has_active"] = any(opt["id"] in selected for opt in gdata["options"])
    return facets


def get_category_facets(
    category: Category,
    current_qs: QuerySet[Product],
    *,
    filter_params: dict | None = None,
) -> dict:
    """Facets for a category listing; cached per category + active filters.

    Prefer ``get_disjunctive_facets`` for interactive filter UIs; this helper
    remains for callers that already have a narrowed ``current_qs``.
    """
    from .facet_cache import facet_cache_key

    cache_key = None
    if filter_params is not None:
        cache_key = facet_cache_key(scope="category-v2", scope_id=category.pk, params=filter_params)
    return get_product_facets(current_qs, cache_key=cache_key)


def get_brands_for_category(categories: QuerySet[Category], *, category_id: int) -> QuerySet:
    """Brands linked to visible products in ``categories`` (cached by category pk)."""
    from .facet_cache import brands_cache_key, get_cached_brand_ids, set_cached_brand_ids
    from .models import Brand

    key = brands_cache_key(category_id=category_id)
    cached_ids = get_cached_brand_ids(key)
    if cached_ids is not None:
        return Brand.objects.filter(pk__in=cached_ids).order_by("name")

    brand_ids = list(
        Brand.objects.filter(
            products__categories__in=categories,
            products__is_visible=True,
        )
        .distinct()
        .order_by("name")
        .values_list("pk", flat=True)
    )
    set_cached_brand_ids(key, brand_ids)
    return Brand.objects.filter(pk__in=brand_ids).order_by("name")


def cached_product_count(
    qs: QuerySet[Product],
    *,
    cache_key: str | None,
) -> int:
    """COUNT for listing headers; optional Redis cache."""
    from .facet_cache import get_cached_count, set_cached_count

    if cache_key:
        cached = get_cached_count(cache_key)
        if cached is not None:
            return cached

    total = qs.count()
    if cache_key:
        set_cached_count(cache_key, total)
    return total


def get_sale_products_queryset() -> QuerySet[Product]:
    """Products on sale: discounted (old_price > price) or in a running promotion."""
    from apps.promotions.services import running_promotions_qs

    discounted_q = Q(
        old_price__isnull=False,
        old_price__gt=F("price"),
    )
    promo_q = Q(pk__in=running_promotions_qs().values("product_id"))
    approved_reviews = Q(reviews__is_approved=True)

    qs = (
        Product.objects.filter(is_visible=True, has_display_image=True)
        .filter(discounted_q | promo_q)
        .exclude(purchase_price__gt=0, price__lt=F("purchase_price"))
    )
    return qs.annotate(
        avg_rating_ann=Avg("reviews__rating", filter=approved_reviews),
        review_count_ann=Count("reviews", filter=approved_reviews),
    ).select_related("brand").prefetch_related("images")


def apply_markup(base_price: Decimal, brand_id: int | None, category_ids: list[int]) -> Decimal:
    """Apply the highest-priority MarkupRule matching brand/category.

    Fallback: when no rule matches, BRAIN_DEFAULT_MARKUP_PERCENT from settings is applied
    (default 0 for Brain-matched prices; used mainly for Kancmaster / manual rules).
    """
    from django.conf import settings

    from .models import MarkupRule

    rules = MarkupRule.objects.filter(is_active=True).order_by("-priority")

    for rule in rules:
        if rule.brand_id and rule.brand_id != brand_id:
            continue
        if rule.category_id and rule.category_id not in category_ids:
            continue
        return rule.apply(base_price)

    default_pct = Decimal(str(getattr(settings, "BRAIN_DEFAULT_MARKUP_PERCENT", 0)))
    if default_pct > 0:
        return (base_price * (Decimal("1") + default_pct / Decimal("100"))).quantize(Decimal("0.01"))
    return base_price
