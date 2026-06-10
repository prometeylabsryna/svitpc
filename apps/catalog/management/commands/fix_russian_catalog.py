"""Replace Russian catalog dictionary labels with Ukrainian (merge duplicates)."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.catalog.ru_localization import run_ru_localization


class Command(BaseCommand):
    help = (
        "Batch-fix Russian labels already in the DB (RU→UK, merge duplicates). "
        "Brain/Kancmaster/OpenCart sync localize on import via localize_ru_to_uk()."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--what",
            choices=["all", "attributegroups", "filtergroups", "attributes", "filters", "productattrs"],
            default="all",
        )
        parser.add_argument("--backend", choices=["google"], default="google")
        parser.add_argument("--dry-run", action="store_true", help="Report counts without writing")
        parser.add_argument("--limit", type=int, default=0, help="Limit rows per step (testing)")

    def handle(self, *args, **options) -> None:
        def on_progress(label: str, done: int, total: int) -> None:
            if done % 500 == 0 or done == total:
                self.stdout.write(f"  {label}: {done}/{total}")

        stats = run_ru_localization(
            what=options["what"],
            backend=options["backend"],
            limit=options["limit"],
            dry_run=options["dry_run"],
            on_progress=on_progress,
        )
        mode = "dry-run" if options["dry_run"] else "done"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: renamed={stats['renamed']} merged={stats['merged']}",
            ),
        )
