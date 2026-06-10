"""Backfill modeltranslation ``*_uk`` columns from legacy base columns."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.core.modeltranslation_sync import backfill_uk_from_legacy


class Command(BaseCommand):
    help = (
        "Copy legacy catalog columns (value, brand name) into modeltranslation "
        "``*_uk`` fields. Safe to re-run."
    )

    def handle(self, *args, **options) -> None:
        stats = backfill_uk_from_legacy()
        for key, count in stats.items():
            self.stdout.write(f"  {key}: {count} rows updated")
        total = sum(stats.values())
        self.stdout.write(self.style.SUCCESS(f"Done: {total} rows updated"))
