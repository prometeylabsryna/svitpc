"""Celery Beat schedule — Europe/Kyiv, heavy imports at night only."""

from __future__ import annotations

from celery.schedules import crontab

# Daytime: prices/stock/metadata only (no image downloads).
_DAYTIME_HOURS = "8,12,16,20"
_STOCK_HOURS = "8,14,20"
_METADATA_HOURS = "9,15"
_TRANSLATE_MAX_ROWS = 1500

CELERY_BEAT_SCHEDULE = {
    # ── Night batch (01:00–10:00 Kyiv) — NP first, then catalog imports ────────
    "novaposhta-sync-cities": {
        "task": "apps.integrations.novaposhta.tasks.sync_np_cities",
        "schedule": crontab(hour=1, minute=0),
    },
    # Full warehouse import (~150 chunks) — weekly only; chunks run on light worker.
    "novaposhta-sync-warehouses": {
        "task": "apps.integrations.novaposhta.tasks.sync_np_warehouses",
        "schedule": crontab(hour=1, minute=10, day_of_week=0),
    },
    "kancmaster-sync": {
        "task": "apps.integrations.kancmaster.tasks.sync_all",
        "schedule": crontab(hour=3, minute=0),
    },
    "brain-sync-categories": {
        "task": "apps.integrations.brain.tasks.sync_categories",
        "schedule": crontab(hour=4, minute=0),
    },
    "brain-sync-products": {
        "task": "apps.integrations.brain.tasks.sync_products",
        "schedule": crontab(hour=4, minute=15),
    },
    # Images + availability chain from sync_products / sync_brain_images_nightly.
    "brain-backfill-descriptions": {
        "task": "apps.integrations.brain.tasks.backfill_descriptions",
        "schedule": crontab(hour=7, minute=30),
        "kwargs": {"reset_cursor": True},
    },
    "brain-sync-description-updates": {
        "task": "apps.integrations.brain.tasks.sync_description_updates",
        "schedule": crontab(hour=7, minute=45),
    },
    "catalog-translate-en": {
        "task": "catalog.translate_to_english",
        "schedule": crontab(hour=12, minute=0),
        "kwargs": {
            "what": "catalog",
            "with_descriptions": True,
            "with_attribute_values": False,
            "max_rows": _TRANSLATE_MAX_ROWS,
        },
    },
    "brain-sync-options": {
        "task": "apps.integrations.brain.tasks.sync_options",
        "schedule": crontab(hour=8, minute=30),
    },
    # ── Daytime (light API passes) ────────────────────────────────────────────
    "brain-sync-prices": {
        "task": "apps.integrations.brain.tasks.sync_prices",
        "schedule": crontab(hour=_DAYTIME_HOURS, minute=5),
    },
    "brain-sync-stock": {
        "task": "apps.integrations.brain.tasks.sync_stock",
        "schedule": crontab(hour=_STOCK_HOURS, minute=10),
    },
    "brain-backfill-metadata": {
        "task": "apps.integrations.brain.tasks.backfill_metadata",
        "schedule": crontab(hour=_METADATA_HOURS, minute=20),
    },
    "brain-reconcile-stale-stock": {
        "task": "apps.integrations.brain.tasks.reconcile_stale_stock",
        "schedule": crontab(hour="11,17", minute=25),
    },
    "brain-sync-new-products": {
        "task": "apps.integrations.brain.tasks.sync_new_products",
        "schedule": crontab(hour="10,16", minute=30),
    },
    # ── Other ─────────────────────────────────────────────────────────────────
    "birthday-greetings": {
        "task": "apps.loyalty.tasks.send_birthday_greetings",
        "schedule": crontab(hour=9, minute=0),
    },
    "expire-old-coins": {
        "task": "apps.loyalty.tasks.expire_old_coins",
        "schedule": crontab(hour=0, minute=30),
    },
    "novaposhta-update-statuses": {
        "task": "apps.shipping.tasks.update_delivery_statuses",
        "schedule": crontab(minute=0),
    },
    "ukrposhta-update-statuses": {
        "task": "apps.integrations.ukrposhta.tasks.update_up_delivery_statuses",
        "schedule": crontab(minute=17, hour="*/1"),
    },
}
