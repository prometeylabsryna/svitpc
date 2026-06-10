"""Import service center price list from Excel workbook."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandParser

from apps.services.price_import import DEFAULT_WORKBOOK, import_service_prices


class Command(BaseCommand):
    help = "Import service center price list from Excel (ТЗ/Прейскурант цен .xlsx)"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--file",
            default=str(DEFAULT_WORKBOOK),
            help="Path to price list .xlsx (default: ТЗ/Прейскурант цен .xlsx)",
        )
        parser.add_argument(
            "--keep-stale",
            action="store_true",
            help="Do not delete price rows missing from the workbook",
        )

    def handle(self, *args, **options) -> None:
        path = Path(options["file"])
        stats = import_service_prices(path, replace=not options["keep_stale"])
        self.stdout.write(
            self.style.SUCCESS(
                "Imported price list: "
                f"{stats['categories']} categories, "
                f"{stats['services']} services, "
                f"{stats['price_items']} price items."
            )
        )
