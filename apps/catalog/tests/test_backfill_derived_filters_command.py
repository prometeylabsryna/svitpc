"""backfill_derived_filters має переживати збій одного товару та дублікати Filter/FilterGroup."""

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.catalog.models import Attribute, AttributeGroup, ProductAttribute, ProductFilter


def _add_attr(product, attr_name: str, value: str, group_name="Характеристики"):
    ag, _ = AttributeGroup.objects.get_or_create(name=group_name)
    attr, _ = Attribute.objects.get_or_create(group=ag, name=attr_name)
    ProductAttribute.objects.create(product=product, attribute=attr, value=value)


@pytest.mark.django_db
def test_survives_single_product_failure_and_processes_rest(product_factory):
    ok_product = product_factory(slug="backfill-ok-1")
    bad_product = product_factory(slug="backfill-bad-1")
    _add_attr(ok_product, "Колір", "Чорний")
    _add_attr(bad_product, "Колір", "Сірий")

    original = "apps.catalog.derived_filters.sync_derived_filters_for_product"

    from apps.catalog.derived_filters import sync_derived_filters_for_product as real_sync

    def flaky(product):
        if product.pk == bad_product.pk:
            raise RuntimeError("boom")
        return real_sync(product)

    out = StringIO()
    with patch(original, side_effect=flaky):
        call_command("backfill_derived_filters", "--skip-dedupe", stdout=out)

    assert ProductFilter.objects.filter(product=ok_product).exists()
    assert not ProductFilter.objects.filter(product=bad_product).exists()
    assert "збоїв: 1" in out.getvalue()


@pytest.mark.django_db
def test_runs_dedupe_by_default(product_factory):
    product = product_factory(slug="backfill-dedupe-1")
    _add_attr(product, "Діагональ", '15.6"')

    out = StringIO()
    with patch("apps.catalog.filter_dedup.dedupe_catalog_filters") as mock_dedupe:
        from apps.catalog.filter_dedup import DedupeStats

        mock_dedupe.return_value = DedupeStats()
        call_command("backfill_derived_filters", stdout=out)

    mock_dedupe.assert_called_once()


@pytest.mark.django_db
def test_skip_dedupe_flag_skips_it(product_factory):
    product = product_factory(slug="backfill-skip-dedupe-1")
    _add_attr(product, "Діагональ", '15.6"')

    out = StringIO()
    with patch("apps.catalog.filter_dedup.dedupe_catalog_filters") as mock_dedupe:
        call_command("backfill_derived_filters", "--skip-dedupe", stdout=out)

    mock_dedupe.assert_not_called()


@pytest.mark.django_db
def test_idempotent_zero_new_links_on_rerun(product_factory):
    product = product_factory(slug="backfill-rerun-1")
    _add_attr(product, "Об'єм SSD", "512 ГБ")

    out1 = StringIO()
    call_command("backfill_derived_filters", "--skip-dedupe", stdout=out1)
    out2 = StringIO()
    call_command("backfill_derived_filters", "--skip-dedupe", stdout=out2)

    assert "нових ProductFilter: 1" in out1.getvalue()
    assert "нових ProductFilter: 0" in out2.getvalue()
