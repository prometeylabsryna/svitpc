import pytest
from django.core.cache import cache

from apps.catalog.facet_cache import (
    catalog_filter_params,
    facet_cache_key,
    get_cached_facets,
    set_cached_facets,
)
from apps.catalog.services import get_product_facets


@pytest.mark.django_db
def test_facet_cache_key_stable() -> None:
    params = catalog_filter_params(
        brand_ids=[2, 1],
        filter_ids=[5],
        price_min=None,
        price_max=None,
        in_stock=False,
        sort="default",
    )
    k1 = facet_cache_key(scope="category", scope_id=10, params=params)
    k2 = facet_cache_key(scope="category", scope_id=10, params=params)
    assert k1 == k2


@pytest.mark.django_db
def test_get_product_facets_uses_cache(
    product_factory, filter_group_factory, filter_factory, product_filter_factory,
) -> None:
    cache.clear()
    group = filter_group_factory(name="Колір")
    filt = filter_factory(name="Чорний", group=group)
    product = product_factory()
    product_filter_factory(product, filt)

    qs = type(product).objects.filter(pk=product.pk)
    key = "catalog:facets:test:1:uk:abc"
    set_cached_facets(key, {99: {"name": "Cached", "options": []}})

    facets = get_product_facets(qs, cache_key=key)
    assert facets[99]["name"] == "Cached"
    assert get_cached_facets(key) is not None
