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

    def test_price_below_purchase_blocked_by_db(self, product_factory):
        """Збиткову ціну неможливо записати навіть через .update() в обхід сигналів:
        CheckConstraint catalog_product_price_above_cost — шар 2 захисту (SEC-09)."""
        from django.db import IntegrityError

        product = product_factory(
            slug="loss-leader",
            price=Decimal("90"),
            old_price=Decimal("100"),
            purchase_price=Decimal("80"),
        )
        with pytest.raises(IntegrityError):
            Product.objects.filter(pk=product.pk).update(price=Decimal("50"))
