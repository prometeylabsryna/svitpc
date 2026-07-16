"""Tests for full Brain availability sync."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.catalog.models import Product
from apps.integrations.brain.availability import sync_all_availability_from_brain


@pytest.mark.django_db
class TestSyncAllAvailabilityFromBrain:
    def test_updates_archive_and_hides_missing(self, product_factory, category_factory):
        root = category_factory(name="Ноутбуки, планшети", slug="ноутбуки-планшети")
        visible = product_factory(
            slug="brain-visible",
            source=Product.SOURCE_BRAIN,
            external_id="100",
            stock=1,
            is_visible=True,
            hide_if_out_of_stock=True,
        )
        archived = product_factory(
            slug="brain-archived",
            source=Product.SOURCE_BRAIN,
            external_id="200",
            stock=1,
            is_visible=True,
            hide_if_out_of_stock=True,
        )
        missing = product_factory(
            slug="brain-missing",
            source=Product.SOURCE_BRAIN,
            external_id="300",
            stock=1,
            is_visible=True,
            hide_if_out_of_stock=False,
        )
        for product in (visible, archived, missing):
            product.categories.add(root)

        client = MagicMock()
        client.get_all_categories.return_value = [
            {"categoryID": 1181, "parentID": 1, "realcat": 0, "name": "Ноутбуки, планшети"},
        ]
        client.get_products.return_value = (
            [
                {"productID": 100, "is_archive": False, "recommendable_price": "999"},
                {"productID": 200, "is_archive": True, "recommendable_price": "999"},
            ],
            2,
        )

        with patch(
            "apps.integrations.brain.availability.brain_hide_out_of_stock_enabled",
            return_value=True,
        ):
            stats = sync_all_availability_from_brain(client, hide_missing=True, dry_run=False)

        visible.refresh_from_db()
        archived.refresh_from_db()
        missing.refresh_from_db()

        assert stats["updated"] == 1
        assert stats["missing_hidden"] == 1
        assert visible.stock == 1 and visible.is_visible is True
        assert archived.stock == 0 and archived.is_visible is False
        assert missing.stock == 0 and missing.is_visible is False

    def test_multi_page_scan_updates_products_on_every_page(
        self, product_factory, category_factory,
    ):
        """Регресія: продукти мапляться пер-сторінково (не однією мапою всього
        каталогу), тож товари з ДРУГОЇ сторінки API мають оновлюватись так
        само, як і з першої."""
        root = category_factory(name="Ноутбуки, планшети", slug="ноутбуки-планшети")
        page1 = product_factory(
            slug="brain-page1", source=Product.SOURCE_BRAIN, external_id="500",
            stock=1, is_visible=True, hide_if_out_of_stock=True,
        )
        page2 = product_factory(
            slug="brain-page2", source=Product.SOURCE_BRAIN, external_id="600",
            stock=1, is_visible=True, hide_if_out_of_stock=True,
        )
        for product in (page1, page2):
            product.categories.add(root)

        client = MagicMock()
        client.get_all_categories.return_value = [
            {"categoryID": 1181, "parentID": 1, "realcat": 0, "name": "Ноутбуки, планшети"},
        ]
        client.get_products.side_effect = [
            ([{"productID": 500, "is_archive": True, "recommendable_price": "999"}], 2),
            ([{"productID": 600, "is_archive": True, "recommendable_price": "999"}], 2),
        ]

        with patch(
            "apps.integrations.brain.availability.products_page_limit",
            return_value=1,
        ), patch(
            "apps.integrations.brain.availability.brain_hide_out_of_stock_enabled",
            return_value=True,
        ):
            stats = sync_all_availability_from_brain(client, hide_missing=False, dry_run=False)

        page1.refresh_from_db()
        page2.refresh_from_db()

        assert stats["updated"] == 2
        assert page1.stock == 0 and page1.is_visible is False
        assert page2.stock == 0 and page2.is_visible is False

    def test_dry_run_does_not_write(self, product_factory, category_factory):
        root = category_factory(name="Ноутбуки, планшети", slug="ноутбуки-планшети")
        product = product_factory(
            slug="brain-dry",
            source=Product.SOURCE_BRAIN,
            external_id="400",
            stock=1,
            is_visible=True,
        )
        product.categories.add(root)

        client = MagicMock()
        client.get_all_categories.return_value = [
            {"categoryID": 1181, "parentID": 1, "realcat": 0, "name": "Ноутбуки, планшети"},
        ]
        client.get_products.return_value = ([{"productID": 400, "is_archive": True}], 1)

        with patch(
            "apps.integrations.brain.availability.brain_hide_out_of_stock_enabled",
            return_value=True,
        ):
            stats = sync_all_availability_from_brain(client, hide_missing=False, dry_run=True)

        product = Product.objects.get(external_id="400")
        assert stats["updated"] == 1
        assert product.stock == 1
        assert product.is_visible is True
