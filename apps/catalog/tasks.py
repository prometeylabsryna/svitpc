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
