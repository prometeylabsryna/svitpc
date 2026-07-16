"""Один битий товар не повинен обривати весь Brain-синк.

Регресійні тести для `_resilient_item` (apps.integrations.brain.tasks) — до
цього будь-яка помилка API/парсингу посеред тисяч товарів валила увесь
nightly/денний прогін (sync_products/sync_prices/sync_stock/sync_options/
sync_new_products/backfill_metadata/reconcile_stale_stock).
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from apps.catalog.models import Product
from apps.integrations.brain.tasks import _resilient_item


class TestResilientItem:
    def test_swallows_plain_exception_and_logs(self, caplog):
        with caplog.at_level("ERROR"):
            with _resilient_item("Brain sync_test", 42):
                raise RuntimeError("boom")
        assert "id=42" in caplog.text

    def test_does_not_swallow_soft_time_limit_exceeded(self):
        with pytest.raises(SoftTimeLimitExceeded):
            with _resilient_item("Brain sync_test", 42):
                raise SoftTimeLimitExceeded()

    def test_normal_completion_does_not_raise(self):
        with _resilient_item("Brain sync_test", 42):
            pass  # no exception — should simply pass through


@pytest.mark.django_db
class TestSyncPricesResilience:
    def _run(self, product_a, product_b, *, fail_id):
        from apps.integrations.brain.tasks import sync_prices

        mock_client = MagicMock()
        mock_client.get_all_vendors.return_value = {}
        mock_client.get_modified_since.return_value = [1001, 1002]

        def fake_get_product(brain_id):
            if brain_id == fail_id:
                raise RuntimeError("Brain API 500")
            return {"categoryID": 1, "price": "999"}

        mock_client.get_product.side_effect = fake_get_product

        with (
            patch("apps.integrations.brain.tasks._brain_client", return_value=mock_client),
            patch("apps.integrations.brain.tasks.build_category_map_from_db", return_value={}),
            patch(
                "apps.integrations.brain.tasks._products_by_external_ids",
                return_value={"1001": product_a, "1002": product_b},
            ),
            patch(
                "apps.integrations.brain.tasks.brain_product_allowed_for_sync", return_value=True,
            ),
            patch(
                "apps.integrations.brain.tasks.apply_detail_to_product", return_value=True,
            ) as mock_apply,
        ):
            sync_prices()

        return mock_apply

    def test_one_failing_item_does_not_abort_the_rest(self, product_factory):
        product_a = product_factory(
            source=Product.SOURCE_BRAIN, external_id="1001", price=Decimal("100"),
        )
        product_b = product_factory(
            source=Product.SOURCE_BRAIN, external_id="1002", price=Decimal("200"),
        )

        mock_apply = self._run(product_a, product_b, fail_id=1001)

        # Товар 1001 впав на client.get_product — apply_detail_to_product НЕ
        # мав викликатись для нього, але 1002 обробився штатно (без цього
        # фіксу виключення на 1001 обірвало б увесь цикл, і 1002 теж
        # лишився б необробленим).
        assert mock_apply.call_count == 1
        assert mock_apply.call_args.args[0] == product_b


@pytest.mark.django_db
class TestSyncNewProductsResilience:
    def test_one_failing_item_does_not_abort_the_rest(self):
        from apps.integrations.brain.tasks import sync_new_products

        mock_client = MagicMock()
        mock_client.get_all_vendors.return_value = {}
        mock_client.get_modified_since.return_value = [2001, 2002]

        def fake_get_product(brain_id):
            if brain_id == 2001:
                raise ConnectionError("timeout")
            return {"productID": brain_id, "name": "Товар", "categoryID": 1}

        mock_client.get_product.side_effect = fake_get_product

        with (
            patch("apps.integrations.brain.tasks._brain_client", return_value=mock_client),
            patch("apps.integrations.brain.tasks.build_category_map_from_db", return_value={}),
            patch("apps.integrations.brain.tasks.is_brain_detail_allowed", return_value=True),
            patch(
                "apps.integrations.brain.tasks.upsert_product_from_detail",
                return_value=(MagicMock(), True),
            ) as mock_upsert,
        ):
            sync_new_products()

        # 2001 впав на get_product ще ДО upsert_product_from_detail — лише
        # 2002 мав дійти до імпорту.
        assert mock_upsert.call_count == 1
        assert mock_upsert.call_args.args[1] == 2002


@pytest.mark.django_db
class TestBackfillMetadataResilience:
    def test_one_failing_item_does_not_abort_the_rest(self, product_factory):
        from apps.integrations.brain.tasks import backfill_metadata

        product_factory(
            source=Product.SOURCE_BRAIN, external_id="3001", brand=None,
        )
        product_b = product_factory(
            source=Product.SOURCE_BRAIN, external_id="3002", brand=None,
        )

        mock_client = MagicMock()
        mock_client.get_all_vendors.return_value = {}

        def fake_get_product(brain_id):
            if brain_id == 3001:
                raise RuntimeError("Brain API 500")
            return {"categoryID": 1}

        mock_client.get_product.side_effect = fake_get_product

        with (
            patch("apps.integrations.brain.tasks._brain_client", return_value=mock_client),
            patch("apps.integrations.brain.tasks.build_category_map_from_db", return_value={}),
            patch(
                "apps.integrations.brain.tasks.filter_brain_products_queryset",
                side_effect=lambda qs: qs,
            ),
            patch(
                "apps.integrations.brain.tasks.apply_detail_to_product", return_value=True,
            ) as mock_apply,
        ):
            backfill_metadata()

        assert mock_apply.call_count == 1
        assert mock_apply.call_args.args[0].pk == product_b.pk
