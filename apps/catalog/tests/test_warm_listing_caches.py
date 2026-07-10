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


@pytest.mark.django_db
def test_warm_listing_caches_includes_direct_children():
    root = Category.objects.create(name="Ноутбуки, планшети", slug="warm-root", is_active=True, is_top=True)
    child = Category.objects.create(name="Ноутбуки", slug="warm-child", is_active=True, parent=root)
    inactive_child = Category.objects.create(
        name="Прихована", slug="warm-hidden-child", is_active=False, parent=root,
    )
    p = Product.objects.create(
        name="Товар у підкатегорії", slug="tovar-warm-child", price=100, stock=3, is_visible=True,
        image_url="https://example.com/photo.jpg",
    )
    p.categories.set([child])

    warmed = warm_listing_caches(limit=5)

    # root + active child warmed; inactive child skipped — still counted at least twice.
    assert warmed >= 2
    assert not Category.objects.filter(pk=inactive_child.pk, is_active=True).exists()
