"""invalidate_catalog_listing_caches має самостійно ставити прогрів у чергу.

Раніше прогрів (`warm_listing_caches`) запускали вручну або лише окремі
викликачі (prune, heavy sync) — забутий/пропущений викликач лишав сайт
з холодним кешем до 15-хвилинного тіку Celery Beat. Тепер прогрів
автоматичний і живе в одному місці — немає ризику розсинхронізації.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.catalog.cache_invalidation import invalidate_catalog_listing_caches


@pytest.mark.django_db
class TestInvalidateCatalogListingCaches:
    def test_schedules_rewarm_by_default(self):
        with patch("apps.catalog.tasks.warm_listing_caches.delay") as mock_delay:
            invalidate_catalog_listing_caches()

        mock_delay.assert_called_once_with()

    def test_rewarm_false_skips_scheduling(self):
        with patch("apps.catalog.tasks.warm_listing_caches.delay") as mock_delay:
            invalidate_catalog_listing_caches(rewarm=False)

        mock_delay.assert_not_called()

    def test_broker_unavailable_does_not_raise(self):
        with patch(
            "apps.catalog.tasks.warm_listing_caches.delay",
            side_effect=RuntimeError("broker down"),
        ):
            invalidate_catalog_listing_caches()  # не має кидати виняток

    def test_clears_nav_cache(self, category_factory, product_factory):
        from django.core.cache import cache

        from apps.catalog.nav import NAV_ORDER_CACHE_KEY, get_top_categories

        cat = category_factory(name="Тест nav", slug="cache-inv-nav", is_top=True)
        product_factory(slug="cache-inv-product").categories.add(cat)
        get_top_categories()  # прогріває NAV_ORDER_CACHE_KEY
        assert cache.get(NAV_ORDER_CACHE_KEY) is not None

        with patch("apps.catalog.tasks.warm_listing_caches.delay"):
            invalidate_catalog_listing_caches()

        assert cache.get(NAV_ORDER_CACHE_KEY) is None
