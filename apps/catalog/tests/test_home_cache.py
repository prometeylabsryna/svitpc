"""Home page product block cache tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.catalog.home_cache import get_home_sale_products
from apps.catalog.models import Product


@pytest.mark.django_db
def test_get_home_sale_products_uses_small_candidate_set(product_factory, settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
    product_factory(
        slug="sale-item",
        price=Decimal("800"),
        old_price=Decimal("1000"),
        image_url="https://cdn.example.com/photo.jpg",
    )
    product_factory(
        slug="regular-item",
        price=Decimal("500"),
        old_price=None,
        image_url="https://cdn.example.com/other.jpg",
    )

    products = get_home_sale_products(limit=6)

    assert len(products) == 1
    assert products[0].slug == "sale-item"
