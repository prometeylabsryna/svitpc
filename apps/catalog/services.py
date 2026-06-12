"""Catalog business logic — filtering, sorting, search helpers."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Avg, Case, Count, F, IntegerField, Q, QuerySet, Value, When
from django.utils import timezone

from apps.core.i18n import localized_field

from .gallery import filter_products_with_display_image
from .models import Category, Filter, Product


def visible_catalog_products() -> QuerySet[Product]:
    """Visible products with a real display photo (no placeholder/stale URLs)."""
    return filter_products_with_display_image(Product.objects.filter(is_visible=True))


def order_stock_first(qs: QuerySet[Product], *order_fields: str) -> QuerySet[Product]:
    """Annotate and order queryset so in-stock products appear before out-of-stock ones."""
    return qs.annotate(
        in_stock_order=Case(
            When(stock__gt=0, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by("in_stock_order", *order_fields)


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
) -> QuerySet[Product]:
    """Apply catalog filters and sorting to a product queryset."""

    qs = filter_products_with_display_image(queryset.filter(is_visible=True))

    if brands:
        qs = qs.filter(brand_id__in=brands)
    if filters:
        # OR within a group, AND between groups:
        # group selected filter IDs by their FilterGroup, then chain one
        # .filter(filters__filter_id__in=[...]) per group so products only
        # need to match *any* value inside a group but *all* selected groups.
        from .models import Filter as FilterModel

        group_map: dict[int, list[int]] = {}
        for row in FilterModel.objects.filter(id__in=filters).values("id", "group_id"):
            group_map.setdefault(row["group_id"], []).append(row["id"])
        for group_filter_ids in group_map.values():
            qs = qs.filter(filters__filter_id__in=group_filter_ids).distinct()
    if price_min is not None:
        qs = qs.filter(price__gte=price_min)
    if price_max is not None:
        qs = qs.filter(price__lte=price_max)
    if in_stock_only:
        qs = qs.filter(stock__gt=0)

    sort_map = {
        "price_asc": "price",
        "price_desc": "-price",
        "new": "-date_added",
        "name_asc": "name",
        "name_desc": "-name",
        "popular": "-viewed",
        "rating": "-avg_rating_ann",
        "default": "sort_order",
    }
    sort_field = sort_map.get(sort, "sort_order")

    if for_count:
        return qs

    if with_reviews_ann:
        # Annotate so product cards avoid N+1 queries when rendering
        # avg_rating / review_count (@property reads these via __dict__ first).
        approved_reviews = Q(reviews__is_approved=True)
        qs = qs.annotate(
            avg_rating_ann=Avg("reviews__rating", filter=approved_reviews),
            review_count_ann=Count("reviews", filter=approved_reviews),
        )

    qs = order_stock_first(qs, sort_field)

    return qs.select_related("brand").prefetch_related("images")


def _compute_product_facets(product_ids: QuerySet[Product]) -> dict:
    """Build facet groups for products matching ``product_ids`` (subquery-safe)."""
    filter_groups = (
        Filter.objects.filter(
            productfilter__product_id__in=product_ids.values("pk"),
            group__is_brand=False,
        )
        .select_related("group")
        .annotate(count=Count("productfilter__product", distinct=True))
        .order_by("group__sort_order", "group__name_uk", "name_uk")
    )

    by_name: dict[str, dict] = {}
    for f in filter_groups:
        gname = localized_field(f.group, "name")
        if gname not in by_name:
            by_name[gname] = {"name": gname, "gid": f.group_id, "options": {}}
        opts = by_name[gname]["options"]
        opt_name = localized_field(f, "name")
        if opt_name not in opts or f.count > opts[opt_name]["count"]:
            opts[opt_name] = {"id": f.id, "name": opt_name, "count": f.count}

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


def get_category_facets(
    category: Category,
    current_qs: QuerySet[Product],
    *,
    filter_params: dict | None = None,
) -> dict:
    """Facets for a category listing; cached per category + active filters."""
    from .facet_cache import facet_cache_key

    cache_key = None
    if filter_params is not None:
        cache_key = facet_cache_key(scope="category", scope_id=category.pk, params=filter_params)
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

    discounted_pks = Product.objects.filter(
        is_visible=True,
        old_price__isnull=False,
        old_price__gt=F("price"),
    ).values_list("pk", flat=True)
    promo_pks = running_promotions_qs().values_list("product_id", flat=True).distinct()
    sale_pks = set(discounted_pks) | set(promo_pks)
    if not sale_pks:
        return Product.objects.none()

    qs = filter_products_with_display_image(
        Product.objects.filter(pk__in=sale_pks, is_visible=True)
    )
    return qs.select_related("brand").prefetch_related("images")


def apply_markup(base_price: Decimal, brand_id: int | None, category_ids: list[int]) -> Decimal:
    """Apply the highest-priority markup rule matching brand/category."""
    from .models import MarkupRule

    rules = MarkupRule.objects.filter(is_active=True).order_by("-priority")

    for rule in rules:
        if rule.brand_id and rule.brand_id != brand_id:
            continue
        if rule.category_id and rule.category_id not in category_ids:
            continue
        return rule.apply(base_price)

    return base_price
