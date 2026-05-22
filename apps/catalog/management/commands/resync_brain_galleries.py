"""Re-fetch product galleries from Brain API (restores multi-photo PDP after cleanup)."""

from django.core.management.base import BaseCommand

from apps.catalog.models import Product
from apps.integrations.brain.services import sync_product_pictures


class Command(BaseCommand):
    help = "Sync ProductImage rows from Brain /product_pictures for all Brain products"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Max products (0 = all)")
        parser.add_argument("--product-id", type=int, default=0, help="Single local product PK")

    def handle(self, *args, **options):
        from apps.integrations.brain.client import BrainAPIClient

        client = BrainAPIClient()
        qs = Product.objects.filter(
            source=Product.SOURCE_BRAIN,
            external_id__gt="",
            is_visible=True,
        ).only("pk", "external_id", "name").order_by("pk")

        if options["product_id"]:
            qs = qs.filter(pk=options["product_id"])
        if options["limit"]:
            qs = qs[: options["limit"]]

        total = qs.count()
        updated = 0
        for product in qs.iterator(chunk_size=200):
            try:
                brain_id = int(product.external_id)
            except (TypeError, ValueError):
                continue
            sync_product_pictures(client, product, brain_id, product.name)
            updated += 1
            if updated % 100 == 0:
                self.stdout.write(f"  … {updated}/{total}")

        self.stdout.write(self.style.SUCCESS(f"Synced galleries for {updated} products."))
