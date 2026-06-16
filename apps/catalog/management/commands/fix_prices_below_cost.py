"""Raise retail prices that sit below purchase cost + markup."""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import F

from apps.catalog.models import Product
from apps.catalog.pricing import enforce_retail_price, minimum_retail_price, reconcile_old_price


class Command(BaseCommand):
    help = "Fix products where shelf price is below purchase cost + MarkupRule (safe, idempotent)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--dry-run", action="store_true", help="Report only, do not write")
        parser.add_argument("--limit", type=int, default=0, help="Max products to scan (0 = all)")

    def handle(self, *args, **options) -> None:
        dry_run: bool = options["dry_run"]
        limit: int = options["limit"]

        qs = (
            Product.objects.filter(purchase_price__gt=0)
            .select_related("brand")
            .prefetch_related("categories")
            .order_by("pk")
        )
        if limit:
            qs = qs[:limit]

        fixed = 0
        scanned = 0
        for product in qs.iterator(chunk_size=200):
            scanned += 1
            cat_ids = list(product.categories.values_list("pk", flat=True))
            minimum = minimum_retail_price(product.purchase_price, product.brand_id, cat_ids)
            if minimum is None or product.price >= minimum:
                continue

            new_price = enforce_retail_price(
                product.price,
                product.purchase_price,
                brand_id=product.brand_id,
                category_ids=cat_ids,
            )
            new_old = reconcile_old_price(new_price, product.old_price)
            fixed += 1
            if dry_run:
                self.stdout.write(
                    f"#{product.pk} {product.slug}: {product.price} -> {new_price} "
                    f"(purchase {product.purchase_price}, min {minimum})"
                )
                continue

            Product.objects.filter(pk=product.pk).update(price=new_price, old_price=new_old)

        suffix = " [dry-run]" if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(f"Scanned {scanned}, fixed {fixed}{suffix}")
        )

        below_cost = Product.objects.filter(
            purchase_price__gt=0,
            price__lt=F("purchase_price"),
        ).count()
        if below_cost and not dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Still {below_cost} products with price < purchase_price "
                    "(no MarkupRule or purchase_price=0 edge cases)."
                )
            )
