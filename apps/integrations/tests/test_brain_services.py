"""Tests for Brain sync services."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.integrations.brain.services import (
    brain_stock_from_detail,
    brain_visibility,
    resolve_brand,
)


@pytest.mark.django_db
class TestBrainServices:
    def test_brain_stock_archive(self):
        assert brain_stock_from_detail({"is_archive": True}) == 0
        assert brain_stock_from_detail({"is_archive": False}) == 1
        assert brain_stock_from_detail({"is_archive": 0}) == 1

    @patch("apps.integrations.brain.services.brain_hide_out_of_stock_enabled", return_value=True)
    def test_brain_visibility_hides_zero_stock(self, _mock):
        assert brain_visibility(0, hide_if_out_of_stock=True) is False
        assert brain_visibility(1, hide_if_out_of_stock=True) is True

    @patch("apps.integrations.brain.services.brain_hide_out_of_stock_enabled", return_value=False)
    def test_brain_visibility_when_policy_off(self, _mock):
        assert brain_visibility(0, hide_if_out_of_stock=True) is True

    def test_resolve_brand(self):
        vendor_map = {107: "KSL"}
        brand = resolve_brand({"vendorID": 107}, vendor_map)
        assert brand is not None
        assert brand.name == "KSL"

    def test_resolve_brand_missing_vendor(self):
        assert resolve_brand({"vendorID": 999}, {1: "X"}) is None

    @pytest.mark.django_db
    def test_apply_detail_updates_price(self):
        from apps.catalog.models import Brand, Product
        from apps.integrations.brain.services import apply_detail_to_product

        brand = Brand.objects.create(name="TestBrand", slug="test-brand")
        product = Product.objects.create(
            source=Product.SOURCE_BRAIN,
            external_id="999001",
            name="Test",
            slug="test-brain-999001",
            price=Decimal("100"),
            stock=1,
            brand=brand,
        )
        detail = {
            "name": "Test",
            "price_uah": "150.00",
            "is_archive": False,
            "vendorID": brand.pk,
        }
        with patch("apps.catalog.services.apply_markup", side_effect=lambda p, *_: p):
            ok = apply_detail_to_product(
                product,
                detail,
                vendor_map={},
                cat_map={},
                update_price=True,
                force_hide_flag=True,
            )
        assert ok
        product.refresh_from_db()
        assert product.purchase_price == Decimal("150.00")
