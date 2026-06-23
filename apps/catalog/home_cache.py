"""Cached product blocks and context for the home page."""

from __future__ import annotations

from typing import Any

from django.core.cache import cache
from django.db.models import F, Q
from django.utils import translation

from apps.promotions.services import with_active_promotions

from .gallery import _valid_image_url_q
from .models import Product
from .services import order_stock_first

HOME_PRODUCTS_CACHE_TTL = 900
_HOME_SALE_SCAN_LIMIT = 80


def _home_cache_key(block: str) -> str:
    lang = translation.get_language() or "uk"
    return f"catalog:home:{block}:{lang}"


def _home_pick_qs():
    """Fast listing queryset for home PK selection (main image URL only, no gallery EXISTS)."""
    return Product.objects.filter(is_visible=True).filter(
        Q(stock__gt=0) | Q(hide_if_out_of_stock=False),
    ).filter(_valid_image_url_q())


def _load_products_by_pks(pks: list[int]) -> list[Product]:
    if not pks:
        return []
    qs = with_active_promotions(
        Product.objects.filter(pk__in=pks).select_related("brand").prefetch_related("images")
    )
    by_pk = {product.pk: product for product in qs}
    return [by_pk[pk] for pk in pks if pk in by_pk]


def _cache_product_block(block: str, pks: list[int]) -> list[Product]:
    cache.set(_home_cache_key(block), pks, HOME_PRODUCTS_CACHE_TTL)
    return _load_products_by_pks(pks)


def _merge_unique_pks(*groups: list[int], limit: int) -> list[int]:
    seen: set[int] = set()
    merged: list[int] = []
    for group in groups:
        for pk in group:
            if pk in seen:
                continue
            seen.add(pk)
            merged.append(pk)
            if len(merged) >= limit:
                return merged
    return merged


def _fill_home_pks(
    primary_pks: list[int],
    *,
    limit: int,
    order_fields: tuple[str, ...],
) -> list[int]:
    if len(primary_pks) >= limit:
        return primary_pks[:limit]
    extra = list(
        order_stock_first(
            _home_pick_qs().exclude(pk__in=primary_pks) if primary_pks else _home_pick_qs(),
            *order_fields,
        ).values_list("pk", flat=True)[: limit - len(primary_pks)]
    )
    return _merge_unique_pks(primary_pks, extra, limit=limit)


def _home_sale_candidate_pks(limit: int) -> list[int]:
    from apps.promotions.services import running_promotions_qs

    discounted = list(
        order_stock_first(
            _home_pick_qs()
            .filter(old_price__isnull=False, old_price__gt=F("price"))
            .exclude(purchase_price__gt=0, price__lt=F("purchase_price")),
            "sort_order",
            "name",
        ).values_list("pk", flat=True)[:_HOME_SALE_SCAN_LIMIT]
    )
    promo = list(
        running_promotions_qs()
        .filter(product__is_visible=True)
        .order_by("-end_date")
        .values_list("product_id", flat=True)
        .distinct()[:_HOME_SALE_SCAN_LIMIT]
    )
    return _merge_unique_pks(discounted, promo, limit=limit)


def get_home_new_products(limit: int = 6) -> list[Product]:
    key = _home_cache_key("new")
    cached = cache.get(key)
    if cached is not None:
        return _load_products_by_pks(cached)

    primary = list(
        order_stock_first(
            _home_pick_qs().filter(is_new=True),
            "sort_order",
            "name",
        ).values_list("pk", flat=True)[:limit]
    )
    pks = _fill_home_pks(primary, limit=limit, order_fields=("-date_added", "-pk"))
    return _cache_product_block("new", pks)


def get_home_hit_products(limit: int = 6) -> list[Product]:
    key = _home_cache_key("hit")
    cached = cache.get(key)
    if cached is not None:
        return _load_products_by_pks(cached)

    primary = list(
        order_stock_first(
            _home_pick_qs().filter(is_hit=True),
            "-viewed",
            "sort_order",
        ).values_list("pk", flat=True)[:limit]
    )
    pks = _fill_home_pks(primary, limit=limit, order_fields=("-viewed", "-pk"))
    return _cache_product_block("hit", pks)


def get_home_sale_products(limit: int = 6) -> list[Product]:
    key = _home_cache_key("sale")
    cached = cache.get(key)
    if cached is not None:
        return _load_products_by_pks(cached)

    pks = _home_sale_candidate_pks(limit)
    return _cache_product_block("sale", pks)


def _cached_home_banners() -> list[Any]:
    from apps.promotions.home_ads import active_home_banners
    from apps.promotions.models import Banner

    key = _home_cache_key("banners")
    pks: list[int] | None = cache.get(key)
    if pks is None:
        pks = list(active_home_banners().values_list("pk", flat=True))
        cache.set(key, pks, HOME_PRODUCTS_CACHE_TTL)
    if not pks:
        return []
    by_pk = Banner.objects.filter(pk__in=pks).in_bulk()
    return [by_pk[pk] for pk in pks if pk in by_pk]


def _cached_home_services(limit: int = 3) -> list[Any]:
    from apps.services.models import Service

    key = _home_cache_key("services")
    pks: list[int] | None = cache.get(key)
    if pks is None:
        pks = list(
            Service.objects.filter(is_active=True, show_on_home=True)
            .order_by("sort_order")
            .values_list("pk", flat=True)[:limit]
        )
        cache.set(key, pks, HOME_PRODUCTS_CACHE_TTL)
    if not pks:
        return []
    qs = Service.objects.filter(pk__in=pks).select_related("category")
    by_pk = {service.pk: service for service in qs}
    return [by_pk[pk] for pk in pks if pk in by_pk]


def get_home_view_context() -> dict[str, Any]:
    """Full home page context with one Redis round-trip when warm."""
    from apps.promotions.home_ads import recommended_banner_size

    bundle_key = _home_cache_key("bundle_v1")
    cached_bundle: dict[str, Any] | None = cache.get(bundle_key)
    if cached_bundle is not None:
        home_ad_columns = cached_bundle["home_ad_columns"]
        home_ads = _cached_home_banners()
    else:
        from apps.promotions.models import HomeAdSettings

        home_ad_columns = HomeAdSettings.load().visible_columns
        home_ads = _cached_home_banners()
        cache.set(
            bundle_key,
            {"home_ad_columns": home_ad_columns},
            HOME_PRODUCTS_CACHE_TTL,
        )

    slot_w, slot_h = recommended_banner_size(home_ad_columns)
    return {
        "new_products": get_home_new_products(),
        "hit_products": get_home_hit_products(),
        "sale_products": get_home_sale_products(),
        "home_services": _cached_home_services(),
        "home_ads": home_ads,
        "home_ad_columns": home_ad_columns,
        "home_ad_slot_width": slot_w,
        "home_ad_slot_height": slot_h,
        "home_ads_carousel": len(home_ads) > home_ad_columns,
    }
