"""Tests for integration product deduplication."""

import pytest
from django.db import connection

from apps.catalog.models import Product
from apps.catalog.product_dedup import dedupe_source_external_id, merge_product_into


def _drop_source_external_id_constraint() -> None:
    """dedupe_* — історичний хелпер для даних ДО constraint (міграція 0018).

    Щоб відтворити дублікати, тимчасово знімаємо constraint; DDL відкотиться
    разом із тестовою транзакцією.
    """
    constraint = next(
        c for c in Product._meta.constraints
        if c.name == "catalog_product_source_external_id_uniq"
    )
    with connection.schema_editor() as editor:
        editor.remove_constraint(Product, constraint)


@pytest.mark.django_db
def test_dedupe_brain_external_id_keeps_one(product_factory):
    _drop_source_external_id_constraint()
    first = product_factory(
        name="Item A",
        slug="brain-dup-a",
        source=Product.SOURCE_BRAIN,
        external_id="9001",
        stock=1,
    )
    second = product_factory(
        name="Item B",
        slug="brain-dup-b",
        source=Product.SOURCE_BRAIN,
        external_id="9001",
        stock=2,
    )
    second.viewed = 10
    second.save(update_fields=["viewed"])

    removed = dedupe_source_external_id(Product.SOURCE_BRAIN, "9001")
    assert removed == 1
    assert Product.objects.filter(source=Product.SOURCE_BRAIN, external_id="9001").count() == 1
    kept = Product.objects.get(source=Product.SOURCE_BRAIN, external_id="9001")
    assert kept.pk == second.pk


@pytest.mark.django_db
def test_merge_product_into_moves_categories(product_factory, category_factory):
    cat = category_factory(name="Cat", slug="cat-merge")
    canonical = product_factory(name="Keep", slug="keep-merge", stock=1)
    duplicate = product_factory(name="Drop", slug="drop-merge", stock=1)
    duplicate.categories.add(cat)

    merge_product_into(canonical, duplicate)
    assert not Product.objects.filter(pk=duplicate.pk).exists()
    assert canonical.categories.filter(pk=cat.pk).exists()
