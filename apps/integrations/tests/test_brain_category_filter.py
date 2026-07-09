"""Tests for Brain category whitelist helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.catalog.models import Category, Product
from apps.integrations.brain.category_filter import (
    allowed_brain_top_categories,
    allowed_local_category_subtree_pks,
    brain_product_allowed_for_sync,
    build_allowed_brain_category_id_set,
    filter_brain_products_queryset,
    get_brain_allowed_category_slugs,
    is_brain_detail_allowed,
)


@pytest.mark.django_db
def test_allowed_brain_top_categories_matches_slug(settings):
    settings.BRAIN_ALLOWED_CATEGORY_SLUGS = "ноутбуки-планшети,канцтовари"
    Category.objects.create(name="Ноутбуки, планшети", slug="ноутбуки-планшети", is_active=True)

    client = MagicMock()
    client.get_all_categories.return_value = [
        {"categoryID": 1, "parentID": 0, "realcat": 0, "name": "Root"},
        {"categoryID": 100, "parentID": 1, "realcat": 0, "name": "Ноутбуки, планшети"},
        {"categoryID": 200, "parentID": 1, "realcat": 0, "name": "Смартфони"},
        {"categoryID": 110, "parentID": 100, "realcat": 0, "name": "Ноутбуки"},
    ]

    tops = allowed_brain_top_categories(client)
    top_ids = {int(c["categoryID"]) for c in tops}
    assert top_ids == {100}

    allowed_ids = build_allowed_brain_category_id_set(client)
    assert allowed_ids == frozenset({100, 110})


def test_is_brain_detail_allowed():
    allowed = frozenset({100, 110})
    assert is_brain_detail_allowed({"categoryID": 110}, allowed)
    assert not is_brain_detail_allowed({"categoryID": 200}, allowed)


@pytest.mark.django_db
def test_filter_brain_products_queryset(product_factory, category_factory):
    root = category_factory(name="Ноутбуки, планшети", slug="ноутбуки-планшети")
    child = category_factory(name="Ноутбуки", slug="ноутбуки", parent=root)
    other = category_factory(name="Смартфони", slug="smartfony")

    allowed_product = product_factory(
        slug="allowed-brain",
        source=Product.SOURCE_BRAIN,
        external_id="1",
    )
    allowed_product.categories.add(child)

    blocked_product = product_factory(
        slug="blocked-brain",
        source=Product.SOURCE_BRAIN,
        external_id="2",
    )
    blocked_product.categories.add(other)

    pks = set(filter_brain_products_queryset(Product.objects.all()).values_list("pk", flat=True))
    assert allowed_product.pk in pks
    assert blocked_product.pk not in pks
    assert root.pk in allowed_local_category_subtree_pks()


@pytest.mark.django_db
def test_brain_product_allowed_for_sync(product_factory, category_factory):
    root = category_factory(name="Канцтовари", slug="канцтовари")
    product = product_factory(source=Product.SOURCE_BRAIN, external_id="55")
    product.categories.add(root)

    allowed_ids = frozenset({999})
    assert brain_product_allowed_for_sync(product, {"categoryID": 999}, allowed_ids)
    assert brain_product_allowed_for_sync(product, {"categoryID": 1}, allowed_ids)
    blocked = product_factory(source=Product.SOURCE_BRAIN, external_id="56")
    assert not brain_product_allowed_for_sync(blocked, {"categoryID": 1}, allowed_ids)


def test_default_slugs_when_setting_empty(settings):
    settings.BRAIN_ALLOWED_CATEGORY_SLUGS = ""
    slugs = get_brain_allowed_category_slugs()
    assert "ноутбуки-планшети" in slugs
    assert "канцтовари" in slugs
    assert "kantseliarski-tovary" not in slugs
