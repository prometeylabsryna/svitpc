"""Tests for retail price floor helpers."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.catalog.models import MarkupRule, Product
from apps.catalog.pricing import enforce_retail_price, minimum_retail_price, reconcile_old_price


@pytest.mark.django_db
def test_enforce_retail_price_uses_markup(db):
    MarkupRule.objects.create(name="Default", markup_percent=Decimal("10"), priority=1)
    result = enforce_retail_price(
        Decimal("90"),
        Decimal("100"),
        brand_id=None,
        category_ids=[],
    )
    assert result == Decimal("110.00")


@pytest.mark.django_db
def test_reconcile_old_price_drops_stale():
    assert reconcile_old_price(Decimal("120"), Decimal("100")) is None
    assert reconcile_old_price(Decimal("100"), Decimal("130")) == Decimal("130")


@pytest.mark.django_db
def test_pre_save_floor_on_product_save(product_factory):
    MarkupRule.objects.create(name="Default", markup_percent=Decimal("15"), priority=1)
    product = product_factory(
        slug="below-cost",
        price=Decimal("80"),
        purchase_price=Decimal("100"),
        old_price=Decimal("90"),
    )
    product.refresh_from_db()
    assert product.price == Decimal("115.00")
    assert product.old_price is None


@pytest.mark.django_db
def test_minimum_retail_without_rules(product_factory):
    assert minimum_retail_price(Decimal("50"), None, []) == Decimal("50")
