"""Re-fetch product galleries from Brain API (restores multi-photo PDP after cleanup)."""

from django.core.management.base import BaseCommand

from apps.catalog.gallery import filter_products_missing_display_image
from apps.catalog.models import Product
from apps.integrations.brain.services import sync_product_pictures


class Command(BaseCommand):
    help = "Sync ProductImage rows from Brain /product_pictures for Brain products"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Max products (0 = all)")
        parser.add_argument("--product-id", type=int, default=0, help="Single local product PK")
        parser.add_argument(
            "--all",
            action="store_true",
            help="Re-sync every Brain product (default: only products missing a photo)",
        )

    def handle(self, *args, **options):
        from apps.integrations.brain.client import BrainAPIClient

        client = BrainAPIClient()
        base = Product.objects.filter(source=Product.SOURCE_BRAIN).exclude(external_id__in=["", "0"])
        qs = base.only("pk", "external_id", "name").order_by("pk")
        if not options["all"]:
            qs = filter_products_missing_display_image(qs)

        if options["product_id"]:
            qs = qs.filter(pk=options["product_id"])
        if options["limit"]:
            qs = qs[: options["limit"]]

        total = qs.count()
        updated = 0
        gained = 0
        from apps.catalog.gallery import resolve_product_image_url

        for product in qs.iterator(chunk_size=200):
            try:
                brain_id = int(product.external_id)
            except (TypeError, ValueError):
                continue
            if brain_id <= 0:
                continue
            had = bool(resolve_product_image_url(product))
            sync_product_pictures(client, product, brain_id, product.name)
            product.refresh_from_db()
            updated += 1
            if not had and resolve_product_image_url(product):
                gained += 1
            if updated % 100 == 0:
                self.stdout.write(f"  … {updated}/{total}")

        self.stdout.write(
            self.style.SUCCESS(f"Synced galleries for {updated} products ({gained} gained a photo)."),
        )
