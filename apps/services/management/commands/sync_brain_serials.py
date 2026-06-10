"""Import serial numbers from Brain report serial_numbers_by_dealer."""

from __future__ import annotations

from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.integrations.brain.client import BrainAPIClient
from apps.services.serial_lookup import normalize_serial
from apps.services.warranty_models import ProductSerial


def _parse_xls_rows(content: bytes) -> list[dict[str, str]]:
    try:
        import xlrd
    except ImportError:
        return []

    book = xlrd.open_workbook(file_contents=content)
    sheet = book.sheet_by_index(0)
    if sheet.nrows < 2:
        return []
    headers = [str(sheet.cell_value(0, c)).strip().lower() for c in range(sheet.ncols)]
    rows: list[dict[str, str]] = []
    for r in range(1, sheet.nrows):
        row = {headers[c]: str(sheet.cell_value(r, c)).strip() for c in range(sheet.ncols) if c < len(headers)}
        rows.append(row)
    return rows


def _parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue
    return None


class Command(BaseCommand):
    help = "Sync serial numbers from Brain API report serial_numbers_by_dealer"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--days", type=int, default=14, help="Date range (max 92)")

    def handle(self, *args, **options) -> None:
        days = min(max(options["days"], 1), 92)
        date_to = timezone.localdate()
        date_from = date_to - timedelta(days=days)
        client = BrainAPIClient()
        raw = client.get_report(
            "serial_numbers_by_dealer",
            date_from=date_from.strftime("%d.%m.%Y"),
            date_to=date_to.strftime("%d.%m.%Y"),
            file_type="xls",
        )
        if raw is None:
            self.stderr.write("Brain report returned no data (check credentials or rate limit).")
            return
        if isinstance(raw, str):
            self.stderr.write("Unexpected HTML report; use file_type=xls.")
            return

        rows = _parse_xls_rows(raw if isinstance(raw, bytes) else raw.encode())
        if not rows:
            self.stderr.write("No rows parsed from XLS (install xlrd or check report format).")
            return

        created = updated = 0
        for row in rows:
            serial_key = next((k for k in row if "серій" in k or "serial" in k), "")
            serial = normalize_serial(row.get(serial_key, ""))
            if not serial:
                continue
            product_name = row.get("товар", "") or row.get("product", "") or row.get("name", "")
            sale_doc = row.get("документ", "") or row.get("document", "")
            sale_date = _parse_date(row.get("дата", "") or row.get("date", ""))
            warranty_until = _parse_date(row.get("гарантія", "") or row.get("warranty", ""))
            defaults = {
                "product_name": product_name[:500],
                "sale_document": sale_doc[:100],
                "sale_date": sale_date,
                "warranty_until": warranty_until,
                "source": ProductSerial.SOURCE_BRAIN,
            }
            _, was_created = ProductSerial.objects.update_or_create(
                serial_number=serial,
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Serials synced: {created} created, {updated} updated"))
