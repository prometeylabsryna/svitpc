"""Tests for Brain category-tree sync: slug-collision disambiguation and
virtual (realcat) category mirroring.

Regression coverage for two real production bugs found in "Комплектуючі до
ПК" (confirmed directly against the live Brain API):

- Brain has TWO distinct real categories both named "Блоки живлення" (one
  under laptop accessories, one under PC components) — slugify() collides,
  and a naive slug-only lookup silently merged desktop PSUs into the
  laptop-charger category.
- Brain represents cross-listing via virtual categories (`realcat > 0`),
  e.g. "SSD диски" under "Комплектуючі до ПК" is a pure alias of "Внутрішні
  SSD" under laptops — products are only ever tagged with the *real*
  categoryID, so the virtual branch stayed permanently empty (404) without
  an explicit mirroring step.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.catalog.models import Category, Product
from apps.integrations.brain.services import (
    build_category_map_from_db,
    sync_brain_categories,
    sync_virtual_category_mirrors,
)


def _client(categories: list[dict]) -> MagicMock:
    client = MagicMock()
    client.get_all_categories.return_value = categories
    return client


@pytest.mark.django_db
class TestSlugCollisionDisambiguation:
    def test_two_same_named_categories_under_different_parents_stay_distinct(self, settings):
        settings.BRAIN_ALLOWED_CATEGORY_SLUGS = "ноутбуки-планшети,комплектуючі-до-пк"
        cats = [
            {"categoryID": 1, "parentID": 0, "realcat": 0, "name": "Root"},
            {"categoryID": 100, "parentID": 1, "realcat": 0, "name": "Ноутбуки, планшети"},
            {"categoryID": 110, "parentID": 100, "realcat": 0, "name": "Аксесуари для ноутбуків"},
            {"categoryID": 111, "parentID": 110, "realcat": 0, "name": "Блоки живлення"},
            {"categoryID": 200, "parentID": 1, "realcat": 0, "name": "Комплектуючі до ПК"},
            {"categoryID": 211, "parentID": 200, "realcat": 0, "name": "Блоки живлення"},
        ]
        client = _client(cats)

        cat_map = sync_brain_categories(client)

        laptop_psu = cat_map[111]
        pc_psu = cat_map[211]
        assert laptop_psu.pk != pc_psu.pk
        assert laptop_psu.slug == "блоки-живлення"
        assert pc_psu.slug == "блоки-живлення-211"
        assert pc_psu.parent_id == cat_map[200].pk
        assert laptop_psu.parent_id == cat_map[110].pk

    def test_second_run_reuses_disambiguated_category_without_duplicating(self, settings):
        settings.BRAIN_ALLOWED_CATEGORY_SLUGS = "ноутбуки-планшети,комплектуючі-до-пк"
        cats = [
            {"categoryID": 1, "parentID": 0, "realcat": 0, "name": "Root"},
            {"categoryID": 100, "parentID": 1, "realcat": 0, "name": "Ноутбуки, планшети"},
            {"categoryID": 110, "parentID": 100, "realcat": 0, "name": "Аксесуари для ноутбуків"},
            {"categoryID": 111, "parentID": 110, "realcat": 0, "name": "Блоки живлення"},
            {"categoryID": 200, "parentID": 1, "realcat": 0, "name": "Комплектуючі до ПК"},
            {"categoryID": 211, "parentID": 200, "realcat": 0, "name": "Блоки живлення"},
        ]
        client = _client(cats)

        first = sync_brain_categories(client)
        second = sync_brain_categories(client)

        assert first[211].pk == second[211].pk
        assert Category.objects.filter(slug__startswith="блоки-живлення").count() == 2

    def test_build_category_map_from_db_prefers_disambiguated_category(self, settings):
        settings.BRAIN_ALLOWED_CATEGORY_SLUGS = "ноутбуки-планшети,комплектуючі-до-пк"
        cats = [
            {"categoryID": 1, "parentID": 0, "realcat": 0, "name": "Root"},
            {"categoryID": 100, "parentID": 1, "realcat": 0, "name": "Ноутбуки, планшети"},
            {"categoryID": 110, "parentID": 100, "realcat": 0, "name": "Аксесуари для ноутбуків"},
            {"categoryID": 111, "parentID": 110, "realcat": 0, "name": "Блоки живлення"},
            {"categoryID": 200, "parentID": 1, "realcat": 0, "name": "Комплектуючі до ПК"},
            {"categoryID": 211, "parentID": 200, "realcat": 0, "name": "Блоки живлення"},
        ]
        client = _client(cats)
        full_map = sync_brain_categories(client)

        # Позначаємо, як це робив би денний light-синк (prices/stock/options),
        # без повного sync_brain_categories() — лише читання з уже наявних
        # у БД категорій.
        light_map = build_category_map_from_db(client)

        assert light_map[211].pk == full_map[211].pk
        assert light_map[211].pk != full_map[111].pk


@pytest.mark.django_db
class TestVirtualCategoryMirrors:
    def _base_cats(self) -> list[dict]:
        return [
            {"categoryID": 1, "parentID": 0, "realcat": 0, "name": "Root"},
            {"categoryID": 100, "parentID": 1, "realcat": 0, "name": "Ноутбуки, планшети"},
            {"categoryID": 120, "parentID": 100, "realcat": 0, "name": "Комплектуючі до ноутбуків"},
            {"categoryID": 121, "parentID": 120, "realcat": 0, "name": "Внутрішні SSD"},
            {"categoryID": 200, "parentID": 1, "realcat": 0, "name": "Комплектуючі до ПК"},
            {"categoryID": 221, "parentID": 200, "realcat": 121, "name": "SSD диски"},
        ]

    def test_mirrors_existing_products_into_virtual_category(self, settings):
        settings.BRAIN_ALLOWED_CATEGORY_SLUGS = "ноутбуки-планшети,комплектуючі-до-пк"
        client = _client(self._base_cats())
        cat_map = sync_brain_categories(client)

        real_cat = cat_map[121]
        assert Category.objects.filter(slug="ssd-диски").exists() is False

        p1 = Product.objects.create(
            source=Product.SOURCE_BRAIN, external_id="1", name="SSD 1",
            slug="ssd-1", price=100, stock=1,
        )
        p1.categories.add(real_cat)
        p2 = Product.objects.create(
            source=Product.SOURCE_BRAIN, external_id="2", name="SSD 2",
            slug="ssd-2", price=100, stock=1,
        )
        p2.categories.add(real_cat)

        added = sync_virtual_category_mirrors(client, cat_map)

        mirror = Category.objects.get(slug="ssd-диски")
        assert mirror.parent_id == cat_map[200].pk
        assert added == 2
        assert set(mirror.products.values_list("pk", flat=True)) == {p1.pk, p2.pk}
        # Товар лишається і у своїй основній (реальній) категорії.
        assert real_cat in p1.categories.all()

    def test_is_idempotent_no_duplicate_links_on_second_run(self, settings):
        settings.BRAIN_ALLOWED_CATEGORY_SLUGS = "ноутбуки-планшети,комплектуючі-до-пк"
        client = _client(self._base_cats())
        cat_map = sync_brain_categories(client)
        real_cat = cat_map[121]

        product = Product.objects.create(
            source=Product.SOURCE_BRAIN, external_id="1", name="SSD 1",
            slug="ssd-1", price=100, stock=1,
        )
        product.categories.add(real_cat)

        first = sync_virtual_category_mirrors(client, cat_map)
        second = sync_virtual_category_mirrors(client, cat_map)

        mirror = Category.objects.get(slug="ssd-диски")
        assert first == 1
        assert second == 0
        assert mirror.products.count() == 1

    def test_skips_when_real_category_not_synced(self, settings):
        settings.BRAIN_ALLOWED_CATEGORY_SLUGS = "комплектуючі-до-пк"
        # "ноутбуки-планшети" НЕ в allowlist → 121 ("Внутрішні SSD") не в cat_map.
        client = _client(self._base_cats())
        cat_map = sync_brain_categories(client)

        added = sync_virtual_category_mirrors(client, cat_map)

        assert added == 0
        assert Category.objects.filter(slug="ssd-диски").exists() is False

    def test_no_products_yet_creates_no_links_but_may_create_mirror_category(self, settings):
        settings.BRAIN_ALLOWED_CATEGORY_SLUGS = "ноутбуки-планшети,комплектуючі-до-пк"
        client = _client(self._base_cats())
        cat_map = sync_brain_categories(client)

        added = sync_virtual_category_mirrors(client, cat_map)

        assert added == 0
