"""Tests for catalog whitelist prune helpers and management command."""

from __future__ import annotations

import pytest
from django.core.management import call_command

from apps.catalog.models import Category, Product


def _ensure_allowed_roots(category_factory) -> Category:
    """Create all default whitelist roots (minimal set for prune validation)."""
    slugs = (
        "ноутбуки-планшети",
        "компютери-аксесуари",
        "комплектуючі-до-пк",
        "тб-аудіо-відео-фото",
        "периферія-оргтехніка",
        "мережеве-обладнання",
        "канцтовари",
        "товари-для-школи",
    )
    roots = []
    for slug in slugs:
        roots.append(category_factory(name=slug, slug=slug))
    return roots[0]


@pytest.mark.django_db
def test_catalog_products_to_prune_keeps_kancmaster_and_allowed(category_factory, product_factory):
    from apps.integrations.brain.category_filter import (
        catalog_products_to_keep_queryset,
        catalog_products_to_prune_queryset,
    )

    allowed_root = category_factory(name="Ноутбуки, планшети", slug="ноутбуки-планшети")
    other_root = category_factory(name="Смартфони", slug="smartfony")

    kanc = product_factory(source=Product.SOURCE_KANCMASTER, external_id="k1", slug="kanc-keep")
    brain_ok = product_factory(source=Product.SOURCE_BRAIN, external_id="b1", slug="brain-keep")
    brain_ok.categories.add(allowed_root)

    brain_bad = product_factory(source=Product.SOURCE_BRAIN, external_id="b2", slug="brain-drop")
    brain_bad.categories.add(other_root)

    orphan = product_factory(source=Product.SOURCE_BRAIN, external_id="b3", slug="brain-orphan")

    keep_pks = set(catalog_products_to_keep_queryset().values_list("pk", flat=True))
    prune_pks = set(catalog_products_to_prune_queryset().values_list("pk", flat=True))

    assert kanc.pk in keep_pks
    assert brain_ok.pk in keep_pks
    assert brain_bad.pk in prune_pks
    assert orphan.pk in prune_pks
    assert kanc.pk not in prune_pks


@pytest.mark.django_db
def test_catalog_products_to_prune_keeps_manual_regardless_of_category(
    category_factory, product_factory,
):
    """Manual products (напр. розділ «Б/У») — це рішення людини, а не залишок
    від фіда постачальника; автопрунінг не повинен їх торкатись, навіть якщо
    їхня категорія поза Brain-whitelist або взагалі без категорії."""
    from apps.integrations.brain.category_filter import (
        catalog_products_to_keep_queryset,
        catalog_products_to_prune_queryset,
    )

    used_root = category_factory(name="Б/У", slug="бу")

    manual_in_used = product_factory(source=Product.SOURCE_MANUAL, slug="manual-used", external_id="m1")
    manual_in_used.categories.add(used_root)

    manual_orphan = product_factory(source=Product.SOURCE_MANUAL, slug="manual-orphan", external_id="m2")

    keep_pks = set(catalog_products_to_keep_queryset().values_list("pk", flat=True))
    prune_pks = set(catalog_products_to_prune_queryset().values_list("pk", flat=True))

    assert manual_in_used.pk in keep_pks
    assert manual_orphan.pk in keep_pks
    assert manual_in_used.pk not in prune_pks
    assert manual_orphan.pk not in prune_pks


@pytest.mark.django_db
def test_prune_disallowed_catalog_products_dry_run(category_factory, product_factory):
    laptops_root = _ensure_allowed_roots(category_factory)
    keep = product_factory(source=Product.SOURCE_BRAIN, slug="keep-me", external_id="10")
    keep.categories.add(laptops_root)
    drop = product_factory(source=Product.SOURCE_BRAIN, slug="drop-me", external_id="11")

    call_command("prune_disallowed_catalog_products", "--dry-run")

    assert Product.objects.filter(pk=keep.pk).exists()
    assert Product.objects.filter(pk=drop.pk).exists()


@pytest.mark.django_db
def test_prune_disallowed_catalog_products_confirm(category_factory, product_factory):
    laptops_root = _ensure_allowed_roots(category_factory)
    kanc_root = category_factory(name="Канцелярські", slug="kantseliarski-tovary")

    kanc = product_factory(source=Product.SOURCE_KANCMASTER, slug="kanc-stay", external_id="k9")
    kanc.categories.add(kanc_root)

    laptop_cat = category_factory(name="Ноутбуки", slug="ноутбуки-cat", parent=laptops_root)
    keep = product_factory(source=Product.SOURCE_BRAIN, slug="laptop-stay", external_id="20")
    keep.categories.add(laptop_cat)

    drop = product_factory(source=Product.SOURCE_BRAIN, slug="phone-go", external_id="21")

    used_root = category_factory(name="Б/У", slug="бу")
    manual_used = product_factory(source=Product.SOURCE_MANUAL, slug="manual-bu", external_id="m5")
    manual_used.categories.add(used_root)

    call_command("prune_disallowed_catalog_products", "--confirm", "--batch-size", "50")

    assert Product.objects.filter(pk=kanc.pk).exists()
    assert Product.objects.filter(pk=keep.pk).exists()
    assert Product.objects.filter(pk=manual_used.pk).exists()
    assert not Product.objects.filter(pk=drop.pk).exists()
