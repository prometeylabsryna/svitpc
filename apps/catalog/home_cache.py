"""Cached product blocks for the home page."""

from __future__ import annotations

from django.core.cache import cache
from django.utils import translation

from apps.promotions.services import with_active_promotions

from .models import Product
from .services import (
    get_sale_products_queryset,
    order_stock_first,
    visible_catalog_products,
)

HOME_PRODUCTS_CACHE_TTL = 600


def _home_cache_key(block: str) -> str:
    lang = translation.get_language() or "uk"
    return f"catalog:home:{block}:{lang}"


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


def _visible_home_qs():
    return with_active_promotions(
        visible_catalog_products().select_related("brand").prefetch_related("images")
    )


def get_home_new_products(limit: int = 6) -> list[Product]:
    key = _home_cache_key("new")
    cached = cache.get(key)
    if cached is not None:
        return _load_products_by_pks(cached)

    visible = _visible_home_qs()
    pks = list(
        order_stock_first(visible.filter(is_new=True), "sort_order", "name")
        .values_list("pk", flat=True)[:limit]
    )
    if len(pks) < limit:
        pks = list(order_stock_first(visible, "-date_added", "-pk").values_list("pk", flat=True)[:limit])
    return _cache_product_block("new", pks)


def get_home_hit_products(limit: int = 6) -> list[Product]:
    key = _home_cache_key("hit")
    cached = cache.get(key)
    if cached is not None:
        return _load_products_by_pks(cached)

    visible = _visible_home_qs()
    pks = list(
        order_stock_first(visible.filter(is_hit=True), "-viewed", "sort_order")
        .values_list("pk", flat=True)[:limit]
    )
    if len(pks) < limit:
        pks = list(order_stock_first(visible, "-viewed", "-pk").values_list("pk", flat=True)[:limit])
    return _cache_product_block("hit", pks)


def get_home_sale_products(limit: int = 6) -> list[Product]:
    key = _home_cache_key("sale")
    cached = cache.get(key)
    if cached is not None:
        return _load_products_by_pks(cached)

    pks = list(
        order_stock_first(with_active_promotions(get_sale_products_queryset()), "sort_order", "name")
        .values_list("pk", flat=True)[:limit]
    )
    return _cache_product_block("sale", pks)
