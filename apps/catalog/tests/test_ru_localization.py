"""Tests for Russian → Ukrainian catalog localization."""

from __future__ import annotations

import pytest

from apps.catalog.models import Attribute, AttributeGroup, Filter, FilterGroup, Product, ProductAttribute, ProductFilter
from apps.catalog.ru_localization import (
    GLOSSARY_RU_UK,
    apply_scoped_renames,
    localize_ru_to_uk,
    merge_scoped_records,
    needs_ru_to_uk,
    ScopedRenameJob,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Производитель", True),
        ("Виробник", False),
        ("EnerGenie", False),
        ("Китай", False),
        ("сенсорное", True),
        ("Вес (г)", True),
        ("Тип", False),
        ("Гарантия, мес", True),
        ("", False),
    ],
)
def test_needs_ru_to_uk(text: str, expected: bool) -> None:
    assert needs_ru_to_uk(text) is expected


def test_glossary_covers_proizvoditel() -> None:
    assert GLOSSARY_RU_UK["Производитель"] == "Виробник"


def test_localize_ru_to_uk_uses_glossary_without_api() -> None:
    assert localize_ru_to_uk("Производитель", allow_api=False) == "Виробник"
    assert localize_ru_to_uk("Виробник", allow_api=False) == "Виробник"


@pytest.mark.django_db
def test_merge_attributes_repoints_product_links() -> None:
    group = AttributeGroup.objects.create(name="Група")
    keep = Attribute.objects.create(group=group, name="Виробник")
    drop = Attribute.objects.create(group=group, name="Производитель")
    product = Product.objects.create(name="Тест", slug="test-merge-attr", price=1)
    ProductAttribute.objects.create(product=product, attribute=drop, value="")

    merge_scoped_records(
        Attribute,
        keep_pk=keep.pk,
        drop_pk=drop.pk,
        link_model=ProductAttribute,
        fk_name="attribute_id",
    )

    assert not Attribute.objects.filter(pk=drop.pk).exists()
    assert ProductAttribute.objects.filter(product=product, attribute=keep).exists()
    assert ProductAttribute.objects.filter(product=product, attribute=drop).count() == 0


@pytest.mark.django_db
def test_apply_scoped_renames_merges_duplicate_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    group = AttributeGroup.objects.create(name="Група")
    a1 = Attribute.objects.create(group=group, name="Производитель")
    a2 = Attribute.objects.create(group=group, name="Виробник")
    product = Product.objects.create(name="Товар", slug="test-scoped-rename", price=10)
    ProductAttribute.objects.create(product=product, attribute=a1, value="")
    ProductAttribute.objects.create(product=product, attribute=a2, value="")

    monkeypatch.setattr(
        "apps.catalog.ru_localization.build_ru_to_uk_map",
        lambda texts, backend="google": {t: "Виробник" for t in texts if t},
    )

    job = ScopedRenameJob("Attributes", Attribute, "group_id", ProductAttribute, "attribute_id")
    renamed, merged = apply_scoped_renames(job, backend="google", dry_run=False)

    assert renamed >= 1
    assert merged >= 1
    assert Attribute.objects.filter(group=group, name="Виробник").count() == 1
    assert ProductAttribute.objects.filter(product=product).count() == 1


@pytest.mark.django_db
def test_apply_scoped_renames_dry_run_no_db_change(monkeypatch: pytest.MonkeyPatch) -> None:
    group = AttributeGroup.objects.create(name="Група")
    attr = Attribute.objects.create(group=group, name="Цвет")

    monkeypatch.setattr(
        "apps.catalog.ru_localization.build_ru_to_uk_map",
        lambda texts, backend="google": {"Цвет": "Колір"},
    )

    job = ScopedRenameJob("Attributes", Attribute, "group_id", ProductAttribute, "attribute_id")
    renamed, _merged = apply_scoped_renames(job, dry_run=True)

    assert renamed >= 1
    attr.refresh_from_db()
    assert attr.name == "Цвет"


@pytest.mark.django_db
def test_merge_filters_dedupes_product_filter() -> None:
    fg = FilterGroup.objects.create(name="Група")
    keep = Filter.objects.create(group=fg, name="Колір")
    drop = Filter.objects.create(group=fg, name="Цвет")
    product = Product.objects.create(name="Товар", slug="test-merge-filter", price=5)
    ProductFilter.objects.create(product=product, filter=drop)

    merge_scoped_records(
        Filter,
        keep_pk=keep.pk,
        drop_pk=drop.pk,
        link_model=ProductFilter,
        fk_name="filter_id",
    )

    assert ProductFilter.objects.filter(product=product, filter=keep).exists()
    assert not Filter.objects.filter(pk=drop.pk).exists()
