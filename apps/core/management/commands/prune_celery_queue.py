"""Prune duplicate / stale tasks from the Celery Redis queue."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.core.celery_queue import inspect_celery_redis_queue, prune_celery_redis_queue


class Command(BaseCommand):
    help = (
        "Remove stale Nova Poshta warehouse chunks and duplicate scheduled tasks "
        "from the Celery broker queue. Stop celery_worker before running."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be removed without changing Redis",
        )
        parser.add_argument(
            "--keep-np-chunks",
            action="store_true",
            help="Do not drop sync_np_warehouses_chunk messages",
        )
        parser.add_argument(
            "--no-dedupe-heavy",
            action="store_true",
            help="Keep duplicate heavy catalog sync messages",
        )
        parser.add_argument(
            "--inspect",
            action="store_true",
            help="Only print queue task counts and exit",
        )

    def handle(self, *args, **options) -> None:
        if options["inspect"]:
            info = inspect_celery_redis_queue()
            self.stdout.write(f"Queue length: {info['length']}")
            for name, count in info["tasks"].items():
                self.stdout.write(f"  {count:4d}  {name}")
            return

        if not options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    "Переконайтесь, що celery_worker зупинено (priority-воркер може працювати)."
                )
            )

        before = inspect_celery_redis_queue()
        self.stdout.write(f"Before: {before['length']} messages")

        stats = prune_celery_redis_queue(
            drop_np_warehouse_chunks=not options["keep_np_chunks"],
            dedupe_heavy=not options["no_dedupe_heavy"],
            dedupe_status=True,
            dry_run=options["dry_run"],
        )

        suffix = " (dry-run)" if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"After{suffix}: {stats.after} messages "
                f"(removed {stats.removed}: np_chunks={stats.dropped_np_chunks}, "
                f"light={stats.dropped_light_routed}, "
                f"duplicates={stats.dropped_duplicates})"
            )
        )
