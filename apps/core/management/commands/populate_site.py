"""One-shot site population: OpenCart SQL + catalog maintenance + integrations.

Mirrors the local dev workflow (import-sql, fix-catalog, Brain, Kancmaster, NP, prices).

Usage:
    python manage.py populate_site
    python manage.py populate_site --sql-file data/my_backup.sql
    python manage.py populate_site --skip-import --full-brain
    python manage.py populate_site --with-translate
"""

from __future__ import annotations

from pathlib import Path

from typing import Callable

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

DEFAULT_SQL = Path("data/svitpc_2023-02-28_15-47-34_backup.sql")
DEFAULT_SQL_STEPS = "brands,categories,attrs,filters,products,specials,images,seo,reviews,flags"
DEFAULT_PRICE_FILE = Path("ТЗ/Прейскурант цен .xlsx")


class Command(BaseCommand):
    help = "Fill the site with catalog and reference data (OpenCart import + post-processing)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--sql-file",
            default=str(DEFAULT_SQL),
            help=f"OpenCart SQL backup path (default: {DEFAULT_SQL})",
        )
        parser.add_argument(
            "--sql-steps",
            default=DEFAULT_SQL_STEPS,
            help="Comma-separated import_opencart_sql steps",
        )
        parser.add_argument(
            "--skip-import",
            action="store_true",
            help="Skip OpenCart SQL import (catalog already loaded)",
        )
        parser.add_argument(
            "--skip-brain",
            action="store_true",
            help="Skip Brain API sync",
        )
        parser.add_argument(
            "--skip-kancmaster",
            action="store_true",
            help="Skip Kancmaster XML sync",
        )
        parser.add_argument(
            "--skip-np",
            action="store_true",
            help="Skip Nova Poshta cities/warehouses sync",
        )
        parser.add_argument(
            "--skip-prices",
            action="store_true",
            help="Skip service price list import",
        )
        parser.add_argument(
            "--skip-catalog-fixes",
            action="store_true",
            help="Skip fix_russian_catalog, dedupe, i18n backfill, search index",
        )
        parser.add_argument(
            "--full-brain",
            action="store_true",
            help="Run full Brain sync_products after brain_setup (slow, needs credentials)",
        )
        parser.add_argument(
            "--with-translate",
            action="store_true",
            help="Run translate_to_english --what=all (Google, may take a long time)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only show planned steps, do not run them",
        )

    def handle(self, *args, **options) -> None:
        steps = self._plan(options)
        if not steps:
            raise CommandError("Nothing to do — check flags and file paths.")

        self.stdout.write("Planned steps:")
        for name, _runner in steps:
            self.stdout.write(f"  • {name}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        for name, runner in steps:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n→ {name}"))
            runner()

        self._print_summary()
        self.stdout.write(self.style.SUCCESS("\npopulate_site finished."))

    def _plan(self, options) -> list[tuple[str, Callable[[], None]]]:
        planned: list[tuple[str, callable]] = []

        planned.append(("Ensure SiteSettings / HomeAdSettings", self._ensure_singletons))

        if not options["skip_import"]:
            sql_path = Path(options["sql_file"])
            if sql_path.is_file():
                steps = options["sql_steps"]
                planned.append(
                    (
                        f"Import OpenCart SQL ({sql_path.name})",
                        lambda p=sql_path, s=steps: call_command(
                            "import_opencart_sql",
                            file=str(p),
                            steps=s,
                        ),
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"SQL file not found: {sql_path} — skipping import "
                        "(use --skip-import if data is already loaded)"
                    )
                )

        if not options["skip_catalog_fixes"]:
            planned.extend(
                [
                    ("Fix Russian catalog labels", lambda: call_command("fix_russian_catalog", what="all")),
                    ("Dedupe catalog filters", lambda: call_command("dedupe_catalog_filters")),
                    ("Backfill modeltranslation *_uk", lambda: call_command("backfill_modeltranslation_uk")),
                    ("Rebuild product search vectors", lambda: call_command("rebuild_product_search_vectors")),
                ]
            )

        if not options["skip_brain"] and self._has_brain():
            planned.append(
                ("Brain setup (policy + categories/metadata backfill)", lambda: call_command("brain_setup", sync_now=True))
            )
            if options["full_brain"]:
                planned.append(("Brain full product sync", self._run_full_brain_sync))
        elif not options["skip_brain"]:
            self.stdout.write(self.style.WARNING("BRAIN_LOGIN/PASSWORD missing — skipping Brain"))

        if not options["skip_kancmaster"] and self._has_kancmaster():
            planned.append(("Kancmaster XML sync", lambda: call_command("sync_kancmaster")))
        elif not options["skip_kancmaster"]:
            self.stdout.write(self.style.WARNING("Kancmaster credentials missing — skipping sync_kancmaster"))

        if not options["skip_np"] and self._has_nova_poshta():
            planned.append(("Nova Poshta cities + warehouses", lambda: call_command("sync_novaposhta")))
        elif not options["skip_np"]:
            self.stdout.write(self.style.WARNING("NOVA_POSHTA_API_KEY missing — skipping sync_novaposhta"))

        if not options["skip_prices"]:
            price_path = DEFAULT_PRICE_FILE
            if price_path.is_file():
                planned.append(
                    (
                        f"Import service prices ({price_path.name})",
                        lambda p=price_path: call_command("import_service_prices", file=str(p)),
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"Price workbook not found: {price_path} — skipping import_service_prices")
                )

        if options["with_translate"]:
            planned.append(
                ("Translate catalog/site to English (Google)", lambda: call_command("translate_to_english", what="all"))
            )

        return planned

    @staticmethod
    def _ensure_singletons() -> None:
        from apps.core.models import SiteSettings
        from apps.promotions.models import HomeAdSettings

        SiteSettings.load()
        HomeAdSettings.load()

    @staticmethod
    def _has_brain() -> bool:
        return bool(getattr(settings, "BRAIN_LOGIN", "") and getattr(settings, "BRAIN_PASSWORD", ""))

    @staticmethod
    def _has_kancmaster() -> bool:
        return bool(
            getattr(settings, "KANCMASTER_XML_URL", "")
            and getattr(settings, "KANCMASTER_LOGIN", "")
            and getattr(settings, "KANCMASTER_PASSWORD", "")
        )

    @staticmethod
    def _has_nova_poshta() -> bool:
        return bool(getattr(settings, "NOVA_POSHTA_API_KEY", ""))

    @staticmethod
    def _run_full_brain_sync() -> None:
        from apps.integrations.brain.tasks import sync_products

        sync_products()

    def _print_summary(self) -> None:
        from apps.catalog.models import Category, Product

        self.stdout.write(
            f"\nCatalog: {Product.objects.count()} products, {Category.objects.count()} categories"
        )
