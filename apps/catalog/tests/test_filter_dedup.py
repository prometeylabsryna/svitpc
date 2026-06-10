"""Tests for OpenCart filter deduplication."""

from __future__ import annotations

import pytest

from apps.catalog.filter_dedup import dedupe_catalog_filters
from apps.catalog.models import Filter, FilterGroup, Product, ProductFilter


@pytest.mark.django_db
def test_dedupe_merges_duplicate_filter_groups() -> None:
    g1 = FilterGroup.objects.create(name="Виробник", sort_order=1, oc_id=1)
    g2 = FilterGroup.objects.create(name="Виробник", sort_order=1, oc_id=2)
    f1 = Filter.objects.create(group=g1, name="AHK", oc_id=10)
    f2 = Filter.objects.create(group=g2, name="AHK", oc_id=11)
    product = Product.objects.create(name="Товар", slug="dedupe-filter-product", price=100)
    ProductFilter.objects.create(product=product, filter=f2)

    stats = dedupe_catalog_filters()

    assert stats.groups_removed == 1
    assert stats.filters_merged == 1
    assert FilterGroup.objects.filter(name="Виробник").count() == 1
    keep_filter = Filter.objects.get(name="AHK")
    assert ProductFilter.objects.filter(product=product, filter=keep_filter).exists()
    assert not FilterGroup.objects.filter(pk=g1.pk).exists()
    assert Filter.objects.filter(name="AHK").count() == 1


@pytest.mark.django_db
def test_dedupe_moves_unique_filters_into_canonical_group() -> None:
    g1 = FilterGroup.objects.create(name="Колір", oc_id=3)
    g2 = FilterGroup.objects.create(name="Колір", oc_id=4)
    red = Filter.objects.create(group=g1, name="червоний", oc_id=20)
    Filter.objects.create(group=g2, name="синій", oc_id=21)

    stats = dedupe_catalog_filters()

    assert stats.groups_removed == 1
    assert stats.filters_moved == 1
    assert FilterGroup.objects.filter(name="Колір").count() == 1
    keep = FilterGroup.objects.get(name="Колір")
    assert set(keep.filters.values_list("name", flat=True)) == {"червоний", "синій"}
    red.refresh_from_db()
    assert red.group_id == keep.pk


@pytest.mark.django_db
def test_dedupe_marks_brand_group() -> None:
    g1 = FilterGroup.objects.create(name="Виробник", oc_id=5, is_brand=False)
    FilterGroup.objects.create(name="Виробник", oc_id=6, is_brand=True)
    Filter.objects.create(group=g1, name="TestBrand", oc_id=30)

    dedupe_catalog_filters()

    g1.refresh_from_db()
    assert g1.is_brand is True


@pytest.mark.django_db
def test_dedupe_dry_run_leaves_database_unchanged() -> None:
    FilterGroup.objects.create(name="Тип", oc_id=7)
    FilterGroup.objects.create(name="Тип", oc_id=8)

    stats = dedupe_catalog_filters(dry_run=True)

    assert stats.groups_removed == 1
    assert FilterGroup.objects.filter(name="Тип").count() == 2
