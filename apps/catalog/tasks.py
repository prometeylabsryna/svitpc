"""Catalog Celery tasks."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)

_TRANSLATE_REQUEUE_SECONDS = 120


@shared_task(name="catalog.flush_product_views")
def flush_product_views() -> int:
    """Скинути накопичені в Redis перегляди товарів у БД (кожні 5 хв)."""
    from apps.catalog.view_counter import flush_product_views as _flush

    updated = _flush()
    if updated:
        logger.info("flush_product_views: %d products updated", updated)
    return updated


@shared_task(name="catalog.warm_listing_caches", soft_time_limit=600, time_limit=900)
def warm_listing_caches(limit: int = 20) -> int:
    """Прогріти COUNT/фасети/бренди топ-категорій і їх прямих підкатегорій.

    Після нічного синку/масового видалення (або просто через TTL=10 хв у тиші)
    кеші скидаються, і перший відвідувач великої категорії (десятки тисяч товарів,
    наприклад «Периферія, оргтехніка» чи «Канцелярські товари») платив кілька
    секунд за холодний COUNT + агрегацію фасетів + список брендів одночасно.
    Прогріваємо всі три кеші для дефолтного стану (без активних фільтрів) —
    це стан, у якому 95%+ відвідувачів відкривають категорію вперше.
    Підкатегорії (наприклад «Ноутбуки» під «Ноутбуки, планшети») — це і є
    сторінки, які реально відкривають користувачі, тому прогріваємо і їх.
    """
    from django.conf import settings
    from django.utils import translation

    from apps.catalog.facet_cache import (
        catalog_filter_params,
        count_cache_key,
        facet_cache_key,
        set_cached_count,
        set_cached_facets,
    )
    from apps.catalog.models import Category
    from apps.catalog.nav import get_top_categories
    from apps.catalog.services import (
        _compute_product_facets,
        category_listing_category_scope,
        category_listing_products,
        get_brands_for_category,
        get_filtered_products,
    )

    params = catalog_filter_params(
        brand_ids=[],
        filter_ids=[],
        price_min=None,
        price_max=None,
        in_stock=False,
        sort="default",
    )

    warmed = 0
    for top_category in get_top_categories(limit=limit):
        children = list(
            Category.objects.filter(parent_id=top_category.pk, is_active=True).only("pk"),
        )
        for category in (top_category, *children):
            qs_lite = get_filtered_products(
                category_listing_products(category),
                for_count=True,
                skip_image_filter=True,
            )
            total = qs_lite.count()
            facets = _compute_product_facets(qs_lite)
            cat_scope = category_listing_category_scope(category)
            get_brands_for_category(cat_scope, category_id=category.pk)

            for lang_code, _name in settings.LANGUAGES:
                with translation.override(lang_code):
                    count_key = count_cache_key(scope="category-v2", scope_id=category.pk, params=params)
                    facets_key = facet_cache_key(scope="category-v2", scope_id=category.pk, params=params)
                set_cached_count(count_key, total)
                set_cached_facets(facets_key, facets)
            warmed += 1

    logger.info(
        "warm_listing_caches: %d categories warmed (count + facets + brands, top + direct children)",
        warmed,
    )
    return warmed


@shared_task(name="catalog.audit_prices_below_cost")
def audit_prices_below_cost() -> None:
    """Нічний аудит: підняти ціни нижче закупівлі + MarkupRule (шар 3 захисту).

    Ловить обходи сигналів (bulk-синки) та товари з даними, що змінились
    після застосування правил. Див. shop_security SEC-09.
    """
    from django.core.management import call_command

    call_command("fix_prices_below_cost")


@shared_task(
    name="catalog.translate_to_english",
    soft_time_limit=3600,
    time_limit=3900,
)
def translate_to_english(
    what: str = "catalog",
    with_descriptions: bool = True,
    with_attribute_values: bool = False,
    max_rows: int = 1500,
) -> int:
    """Fill missing English fields; re-queues itself when more rows remain."""
    from apps.integrations.heavy_sync import heavy_catalog_sync_lock

    with heavy_catalog_sync_lock("translate_en") as acquired:
        if not acquired:
            return 0
        total = _run_translate_to_english(
            what=what,
            with_descriptions=with_descriptions,
            with_attribute_values=with_attribute_values,
            max_rows=max_rows,
        )
        if max_rows and total >= max_rows:
            from apps.catalog.content_translation import has_pending_catalog_translation

            if has_pending_catalog_translation(
                with_descriptions=with_descriptions,
                with_attribute_values=with_attribute_values,
            ):
                translate_to_english.apply_async(
                    countdown=_TRANSLATE_REQUEUE_SECONDS,
                    kwargs={
                        "what": what,
                        "with_descriptions": with_descriptions,
                        "with_attribute_values": with_attribute_values,
                        "max_rows": max_rows,
                    },
                )
                logger.info(
                    "catalog.translate_to_english: re-queued in %ss after %d rows",
                    _TRANSLATE_REQUEUE_SECONDS,
                    total,
                )
        return total


def _run_translate_to_english(
    *,
    what: str,
    with_descriptions: bool,
    with_attribute_values: bool,
    max_rows: int,
) -> int:
    from apps.catalog.content_translation import run_catalog_translation

    total = run_catalog_translation(
        what=what,
        with_descriptions=with_descriptions,
        with_attribute_values=with_attribute_values,
        max_rows=max_rows,
    )
    logger.info("catalog.translate_to_english: %d fields updated (what=%s)", total, what)
    return total
