"""Full Brain availability resync — fixes stale in-stock flags and hidden archives."""

from django.core.management.base import BaseCommand

from apps.integrations.brain.availability import sync_all_availability_from_brain
from apps.integrations.brain.client import BrainAPIClient
from apps.integrations.brain.tasks import apply_hide_out_of_stock_policy


class Command(BaseCommand):
    help = (
        "Resync Brain is_archive for the whole catalog (not only recently modified). "
        "Optionally hide local Brain products missing from Brain lists."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report counts only, do not write to the database",
        )
        parser.add_argument(
            "--keep-missing",
            action="store_true",
            help="Do not hide Brain products absent from the API catalog scan",
        )
        parser.add_argument(
            "--apply-policy",
            action="store_true",
            help="Run apply_hide_out_of_stock_policy after sync",
        )

    def handle(self, *args, **options) -> None:
        dry_run: bool = options["dry_run"]
        hide_missing = not options["keep_missing"]

        client = BrainAPIClient()
        stats = sync_all_availability_from_brain(
            client,
            hide_missing=hide_missing,
            dry_run=dry_run,
        )

        suffix = " [dry-run]" if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Brain API rows: {stats['scanned_api']}, "
                f"updated: {stats['updated']}, "
                f"missing hidden: {stats['missing_hidden']}, "
                f"visible with zero stock: {stats['still_visible_zero_stock']}{suffix}"
            )
        )

        if options["apply_policy"] and not dry_run:
            apply_hide_out_of_stock_policy()
            self.stdout.write(self.style.SUCCESS("Applied hide-out-of-stock policy"))
