"""Smoke test for the post-sync COUNT cache warmup task."""

import pytest

from apps.catalog.models import Category, Product
from apps.catalog.tasks import warm_listing_caches


@pytest.mark.django_db
def test_warm_listing_caches_smoke():
    cat = Category.objects.create(name="Тест", slug="test-warm", is_active=True, is_top=True)
    p = Product.objects.create(
        name="Товар", slug="tovar-warm", price=100, stock=3, is_visible=True,
        image_url="https://example.com/photo.jpg",
    )
    p.categories.set([cat])

    warmed = warm_listing_caches(limit=5)
    assert warmed >= 1


@pytest.mark.django_db
def test_warm_listing_caches_empty_catalog():
    assert warm_listing_caches(limit=5) == 0
