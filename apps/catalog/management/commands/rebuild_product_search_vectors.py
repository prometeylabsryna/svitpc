"""Backfill precomputed ``Product.search_vector`` for fast catalog search."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.catalog.models import Product
from apps.catalog.search_index import refresh_product_search_vectors


class Command(BaseCommand):
    help = "Rebuild PostgreSQL FTS search_vector for catalog products."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--batch-size",
            type=int,
            default=2000,
            help="Products per batch when using --visible-only (default: 2000).",
        )
        parser.add_argument(
            "--visible-only",
            action="store_true",
            help="Only visible products (recommended after initial full rebuild).",
        )

    def handle(self, *args, **options) -> None:
        batch_size: int = options["batch_size"]
        qs = Product.objects.all()
        if options["visible_only"]:
            qs = qs.filter(is_visible=True)

        total = qs.count()
        if total == 0:
            self.stdout.write("No products to index.")
            return

        updated = 0
        if options["visible_only"] and total > batch_size:
            pks = qs.values_list("pk", flat=True).iterator(chunk_size=batch_size)
            batch: list[int] = []
            for pk in pks:
                batch.append(pk)
                if len(batch) >= batch_size:
                    updated += refresh_product_search_vectors(Product.objects.filter(pk__in=batch))
                    self.stdout.write(f"  … {updated}/{total}")
                    batch = []
            if batch:
                updated += refresh_product_search_vectors(Product.objects.filter(pk__in=batch))
        else:
            updated = refresh_product_search_vectors(qs)

        self.stdout.write(self.style.SUCCESS(f"Indexed {updated} product(s)."))
