"""Tests for the remove_legacy_root_categories management command."""

from __future__ import annotations

import pytest
from django.core.management import call_command

from apps.catalog.models import Category, Product


@pytest.mark.django_db
class TestRemoveLegacyRootCategories:
    def test_dry_run_deletes_nothing(self, category_factory, product_factory, capsys):
        root = category_factory(name="Гаджети (Hi-Tech)", slug="гаджети-hi-tech")
        product = product_factory(source=Product.SOURCE_BRAIN, external_id="g1", slug="gadget-1")
        product.categories.add(root)

        call_command("remove_legacy_root_categories", "--dry-run")

        assert Category.objects.filter(pk=root.pk).exists()
        assert Product.objects.filter(pk=product.pk).exists()
        out = capsys.readouterr().out
        assert "DRY RUN" in out

    def test_confirm_deletes_category_tree_and_products(self, category_factory, product_factory):
        root = category_factory(name="Торгівельне обладнання", slug="торгівельне-обладнання")
        child = category_factory(name="Калькулятори", slug="kalkuliatory", parent=root)
        product = product_factory(source=Product.SOURCE_KANCMASTER, external_id="k1", slug="calc-1")
        product.categories.add(child)

        untouched_root = category_factory(name="Ноутбуки, планшети", slug="ноутбуки-планшети")
        untouched_product = product_factory(source=Product.SOURCE_KANCMASTER, external_id="k2", slug="laptop-1")
        untouched_product.categories.add(untouched_root)

        call_command("remove_legacy_root_categories", "--confirm")

        assert not Category.objects.filter(pk=root.pk).exists()
        assert not Category.objects.filter(pk=child.pk).exists()
        assert not Product.objects.filter(pk=product.pk).exists()

        assert Category.objects.filter(pk=untouched_root.pk).exists()
        assert Product.objects.filter(pk=untouched_product.pk).exists()

    def test_noop_when_categories_already_absent(self, capsys):
        call_command("remove_legacy_root_categories", "--dry-run")

        out = capsys.readouterr().out
        assert "Нічого видаляти" in out

    def test_product_in_both_legacy_and_allowed_category_is_still_removed(
        self, category_factory, product_factory,
    ):
        """Явна вимога: товар видаляється, навіть якщо він додатково прив'язаний
        до дозволеної категорії — легасі-категорія прибирається без винятків."""
        legacy_root = category_factory(name="Гаджети (Hi-Tech)", slug="гаджети-hi-tech")
        allowed_root = category_factory(name="Ноутбуки, планшети", slug="ноутбуки-планшети")
        product = product_factory(source=Product.SOURCE_BRAIN, external_id="g2", slug="gadget-2")
        product.categories.add(legacy_root, allowed_root)

        call_command("remove_legacy_root_categories", "--confirm")

        assert not Category.objects.filter(pk=legacy_root.pk).exists()
        assert not Product.objects.filter(pk=product.pk).exists()
        assert Category.objects.filter(pk=allowed_root.pk).exists()
