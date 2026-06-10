"""Merge duplicate filter groups and filter values imported from OpenCart."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.catalog.filter_dedup import dedupe_catalog_filters


class Command(BaseCommand):
    help = (
        "Merge duplicate FilterGroup / Filter rows that share the same normalized name "
        "(OpenCart legacy: one group per category). Re-links ProductFilter rows."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report counts without writing to the database",
        )

    def handle(self, *args, **options) -> None:
        dry_run = options["dry_run"]
        stats = dedupe_catalog_filters(dry_run=dry_run)
        mode = "dry-run" if dry_run else "done"
        payload = ", ".join(f"{key}={value}" for key, value in stats.as_dict().items())
        self.stdout.write(self.style.SUCCESS(f"{mode}: {payload}"))
