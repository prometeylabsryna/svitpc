"""Build catalog spec filters (CPU, RAM, SSD, …) from Brain product attributes."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.catalog.models import Product
from apps.catalog.spec_filters import sync_spec_filters_from_attributes

_BATCH = 500


class Command(BaseCommand):
    help = (
        "Populate ProductFilter facets for Діагональ, Процесор, RAM, Відеокарта, SSD, Колір "
        "from existing Brain product attributes."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max products to process (0 = all)",
        )
        parser.add_argument(
            "--category-slug",
            default="",
            help="Only products in this category subtree (e.g. ноутбуки-планшети)",
        )

    def handle(self, *args, **options) -> None:
        from apps.catalog.filter_dedup import dedupe_catalog_filters

        limit = int(options["limit"] or 0)
        category_slug = (options["category_slug"] or "").strip()

        self.stdout.write("Merging duplicate filter groups (OpenCart legacy)…")
        dedupe_stats = dedupe_catalog_filters()
        self.stdout.write(
            f"dedupe: groups_merged={dedupe_stats.groups_merged}, "
            f"filters_merged={dedupe_stats.filters_merged}",
        )

        qs = (
            Product.objects.filter(source=Product.SOURCE_BRAIN, is_visible=True)
            .prefetch_related("attributes__attribute")
            .order_by("pk")
        )
        if category_slug:
            from apps.catalog.models import Category

            category = Category.objects.filter(slug=category_slug, is_active=True).first()
            if not category:
                self.stderr.write(self.style.ERROR(f"Category not found: {category_slug}"))
                return
            qs = qs.filter(
                categories__tree_id=category.tree_id,
                categories__lft__gte=category.lft,
                categories__rght__lte=category.rght,
            ).distinct()

        if limit > 0:
            qs = qs[:limit]

        total = qs.count()
        updated = 0
        linked = 0
        self.stdout.write(f"Processing {total} products…")

        batch: list[Product] = []
        for product in qs.iterator(chunk_size=_BATCH):
            batch.append(product)
            if len(batch) < _BATCH:
                continue
            u, l = self._process_batch(batch)
            updated += u
            linked += l
            batch.clear()

        if batch:
            u, l = self._process_batch(batch)
            updated += u
            linked += l

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {updated} products with new filter links, {linked} new ProductFilter rows",
            )
        )

    def _process_batch(self, products: list[Product]) -> tuple[int, int]:
        updated = 0
        linked = 0
        for product in products:
            n = sync_spec_filters_from_attributes(product)
            if n:
                updated += 1
                linked += n
        return updated, linked
