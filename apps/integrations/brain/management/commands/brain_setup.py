"""One-time / maintenance setup for Brain integration after OC import."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Enable Brain out-of-stock policy and enqueue metadata/stock backfill tasks"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync-now",
            action="store_true",
            help="Run apply_hide_out_of_stock_policy synchronously (no Celery)",
        )
        parser.add_argument(
            "--enqueue",
            action="store_true",
            help="Enqueue backfill + reconcile Celery tasks (default when neither flag)",
        )

    def handle(self, *args, **options):
        from apps.integrations.brain.tasks import (
            apply_hide_out_of_stock_policy,
            backfill_metadata,
            reconcile_stale_stock,
            sync_categories,
        )

        run_sync = options["sync_now"]
        enqueue = options["enqueue"] or not run_sync

        if run_sync:
            apply_hide_out_of_stock_policy()
            self.stdout.write(self.style.SUCCESS("Applied hide-out-of-stock policy"))
        elif enqueue:
            apply_hide_out_of_stock_policy.delay()
            sync_categories.delay()
            backfill_metadata.delay()
            reconcile_stale_stock.delay()
            self.stdout.write(
                self.style.SUCCESS(
                    "Enqueued: apply_hide_out_of_stock_policy, sync_categories, "
                    "backfill_metadata, reconcile_stale_stock"
                )
            )
