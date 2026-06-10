"""Set Product.old_price from Brain retail_price_uah for existing Brain products."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandParser

from apps.catalog.models import Product
from apps.integrations.brain.client import BrainAPIClient
from apps.integrations.brain.services import (
    apply_detail_to_product,
    brain_sale_old_price,
    build_category_map_from_db,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill old_price from Brain RRP (retail_price_uah / recommendable_price) for sale listings"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--limit", type=int, default=0, help="Max products to process (0 = all)")
        parser.add_argument("--dry-run", action="store_true", help="Count only, do not write")

    def handle(self, *args, **options) -> None:
        limit: int = options["limit"]
        dry_run: bool = options["dry_run"]

        qs = (
            Product.objects.filter(source=Product.SOURCE_BRAIN, is_visible=True)
            .exclude(external_id="")
            .select_related("brand")
            .prefetch_related("categories")
        )
        if limit:
            qs = qs[:limit]

        total = qs.count()
        if not total:
            self.stdout.write("No Brain products to process.")
            return

        client = BrainAPIClient()
        vendor_map: dict[int, str] = {}
        cat_map = build_category_map_from_db()
        updated = 0
        skipped = 0
        errors = 0

        for product in qs.iterator(chunk_size=50):
            try:
                brain_id = int(product.external_id)
            except (TypeError, ValueError):
                skipped += 1
                continue

            try:
                detail = client.get_product(brain_id, lang="ua")
            except Exception:
                logger.exception("Brain get_product failed for %s", product.external_id)
                errors += 1
                continue

            if not detail:
                skipped += 1
                continue

            price_raw = Decimal(str(detail.get("price_uah") or detail.get("price") or 0))
            cat_ids = list(product.categories.values_list("pk", flat=True))
            old = brain_sale_old_price(detail, price_raw, product.brand_id, cat_ids)

            if old is None or old <= product.price:
                skipped += 1
                continue

            if dry_run:
                updated += 1
                continue

            if apply_detail_to_product(
                product,
                detail,
                vendor_map=vendor_map,
                cat_map=cat_map,
                update_price=False,
                update_stock=False,
                update_brand=False,
                update_category=False,
                update_image=False,
            ):
                updated += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {updated} with sale price, {skipped} skipped, {errors} errors (of {total})"
                + (" [dry-run]" if dry_run else "")
            )
        )
