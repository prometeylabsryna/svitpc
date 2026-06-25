"""Catalog Celery tasks."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="catalog.translate_to_english")
def translate_to_english(
    what: str = "catalog",
    with_descriptions: bool = True,
    with_attribute_values: bool = False,
) -> int:
    """Fill missing English fields for catalog (and optionally site) content."""
    from apps.integrations.heavy_sync import heavy_catalog_sync_lock

    with heavy_catalog_sync_lock("translate_en") as acquired:
        if not acquired:
            return 0
        return _run_translate_to_english(
            what=what,
            with_descriptions=with_descriptions,
            with_attribute_values=with_attribute_values,
        )


def _run_translate_to_english(
    *,
    what: str,
    with_descriptions: bool,
    with_attribute_values: bool,
) -> int:
    from apps.catalog.content_translation import run_catalog_translation

    total = run_catalog_translation(
        what=what,
        with_descriptions=with_descriptions,
        with_attribute_values=with_attribute_values,
    )
    logger.info("catalog.translate_to_english: %d fields updated (what=%s)", total, what)
    return total
