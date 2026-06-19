"""Tests for Brain sync services."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.integrations.brain.services import (
    brain_customer_old_price,
    brain_customer_price,
    brain_shelf_prices,
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

    def test_brain_customer_price_uses_retail_rrp(self):
        detail = {"price_uah": "227555", "retail_price_uah": "230120"}
        assert brain_customer_price(detail) == Decimal("230120.00")

    def test_brain_customer_price_promo_uses_recommendable(self):
        detail = {
            "price_uah": "100",
            "retail_price_uah": "140",
            "recommendable_price": "100",
        }
        assert brain_customer_price(detail) == Decimal("100.00")
        assert brain_customer_old_price(detail) == Decimal("140.00")

    def test_brain_customer_old_price_none_without_promo(self):
        detail = {"price_uah": "227555", "retail_price_uah": "230120"}
        shelf = brain_customer_price(detail)
        assert brain_customer_old_price(detail, shelf) is None

    def test_brain_shelf_prices_tuple(self):
        detail = {
            "price_uah": "100",
            "retail_price_uah": "140",
            "recommendable_price": "100",
        }
        shelf, old, wholesale = brain_shelf_prices(detail)
        assert shelf == Decimal("100.00")
        assert old == Decimal("140.00")
        assert wholesale == Decimal("100.00")

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
            "retail_price_uah": "180.00",
            "is_archive": False,
            "vendorID": brand.pk,
        }
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
        assert product.price == Decimal("180.00")

    @pytest.mark.django_db
    def test_apply_detail_sets_old_price_from_brain_promo(self):
        from apps.catalog.models import Product
        from apps.integrations.brain.services import apply_detail_to_product

        product = Product.objects.create(
            source=Product.SOURCE_BRAIN,
            external_id="999002",
            name="Retail test",
            slug="retail-test-999002",
            price=Decimal("100"),
            stock=1,
        )
        detail = {
            "name": "Retail test",
            "price_uah": "100",
            "retail_price_uah": "140",
            "recommendable_price": "100",
            "is_archive": False,
        }
        apply_detail_to_product(
            product,
            detail,
            vendor_map={},
            cat_map={},
            update_price=True,
        )
        product.refresh_from_db()
        assert product.price == Decimal("100")
        assert product.old_price == Decimal("140")

    @pytest.mark.django_db
    def test_sync_product_pictures_keeps_existing_on_empty_brain_response(self):
        from apps.catalog.models import Product, ProductImage
        from apps.integrations.brain.services import sync_product_pictures

        product = Product.objects.create(
            source=Product.SOURCE_BRAIN,
            external_id="999003",
            name="Photo keep",
            slug="photo-keep-999003",
            price=Decimal("100"),
            stock=1,
            image_url="https://cdn.example.com/keep.jpg",
        )
        ProductImage.objects.create(
            product=product,
            image_url="https://cdn.example.com/keep.jpg",
            sort_order=0,
        )
        client = MagicMock()
        client.get_product_pictures.return_value = []

        sync_product_pictures(client, product, 999003, product.name)

        product.refresh_from_db()
        assert product.image_url == "https://cdn.example.com/keep.jpg"
        assert product.images.count() == 1
