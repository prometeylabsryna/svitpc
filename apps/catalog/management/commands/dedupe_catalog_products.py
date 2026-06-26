"""Management command: merge duplicate catalog products by source + external_id."""

from django.core.management.base import BaseCommand

from apps.catalog.product_dedup import dedupe_all_integration_products


class Command(BaseCommand):
    help = "Merge duplicate integration products (same source + external_id)."

    def handle(self, *args, **options):
        removed = dedupe_all_integration_products()
        self.stdout.write(self.style.SUCCESS(f"Merged {removed} duplicate product row(s)."))
