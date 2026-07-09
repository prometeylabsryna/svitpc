"""Tests for Brain Celery tasks."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.catalog.models import Product


@pytest.mark.django_db
def test_sync_prices_hides_zero_price_brain_products(product_factory, category_factory):
    """Regression: sync_prices must import Product before hide-zero query."""
    root = category_factory(name="Ноутбуки, планшети", slug="ноутбуки-планшети")
    visible_zero = product_factory(
        source=Product.SOURCE_BRAIN,
        external_id="1001",
        price=Decimal("0"),
        is_visible=True,
    )
    visible_zero.categories.add(root)
    other = product_factory(
        source=Product.SOURCE_BRAIN,
        external_id="1002",
        price=Decimal("500"),
        is_visible=True,
    )
    other.categories.add(root)

    mock_client = MagicMock()
    mock_client.get_all_vendors.return_value = {}
    mock_client.get_all_categories.return_value = [
        {"categoryID": 1181, "parentID": 1, "realcat": 0, "name": "Ноутбуки, планшети"},
    ]
    mock_client.get_modified_since.return_value = [1001, 1002]
    mock_client.get_product.return_value = None

    with (
        patch("apps.integrations.brain.tasks._brain_client", return_value=mock_client),
        patch("apps.integrations.brain.tasks.build_category_map_from_db", return_value={}),
        patch(
            "apps.integrations.brain.tasks._products_by_external_ids",
            return_value={
                "1001": visible_zero,
            },
        ),
    ):
        from apps.integrations.brain.tasks import sync_prices

        sync_prices()

    visible_zero.refresh_from_db()
    assert visible_zero.is_visible is False
