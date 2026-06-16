from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from apps.catalog.models import Product
from apps.catalog.services import get_sale_products_queryset


@pytest.mark.django_db
class TestGetSaleProductsQueryset:
    def test_includes_discounted_products(self, product_factory):
        product_factory(
            slug="discounted",
            price=Decimal("800"),
            old_price=Decimal("1000"),
        )
        product_factory(slug="regular", price=Decimal("500"), old_price=None)

        pks = set(get_sale_products_queryset().values_list("pk", flat=True))
        assert Product.objects.get(slug="discounted").pk in pks
        assert Product.objects.get(slug="regular").pk not in pks

    def test_excludes_price_below_purchase(self, product_factory):
        product_factory(
            slug="loss-leader",
            price=Decimal("50"),
            old_price=Decimal("100"),
            purchase_price=Decimal("80"),
        )
        pks = set(get_sale_products_queryset().values_list("pk", flat=True))
        assert Product.objects.get(slug="loss-leader").pk not in pks
