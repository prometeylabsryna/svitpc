"""Recalculate shelf prices for all Brain-sourced products using the new pricing logic.

The command uses data already in the database:
  - purchase_price  = Brain wholesale (price_uah)
  - old_price       = Brain retail (was stored as old_price under the broken 0%-markup logic)

New logic:  shelf = apply_markup(retail)  where retail = old_price (if > purchase_price)
            OR apply_markup(purchase_price) when retail is unknown.

Run BEFORE Brain full-sync so existing products are fixed immediately.

Usage:
    python manage.py recalculate_brain_prices --dry-run
    python manage.py recalculate_brain_prices --confirm
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

logger = logging.getLogger(__name__)

BATCH = 500


class Command(BaseCommand):
    help = "Перерахувати ціни всіх Brain-товарів: retail * (1 + markup%) замість wholesale"

    def add_arguments(self, parser: CommandParser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--dry-run", action="store_true", help="Показати зміни, нічого не писати")
        group.add_argument("--confirm", action="store_true", help="Застосувати зміни")
        parser.add_argument(
            "--chunk",
            type=int,
            default=BATCH,
            help=f"Розмір батчу UPDATE (default {BATCH})",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from django.conf import settings

        from apps.catalog.models import Product
        from apps.catalog.services import apply_markup
        from apps.catalog.pricing import reconcile_old_price

        dry_run: bool = options["dry_run"]
        chunk: int = options["chunk"]

        default_pct = getattr(settings, "BRAIN_DEFAULT_MARKUP_PERCENT", 5)
        self.stdout.write(f"[recalculate_brain_prices] dry_run={dry_run}, default_markup={default_pct}%")

        qs = Product.objects.filter(
            source=Product.SOURCE_BRAIN,
            purchase_price__isnull=False,
            purchase_price__gt=0,
        ).only("pk", "price", "old_price", "purchase_price", "brand_id")

        total = qs.count()
        self.stdout.write(f"Brain products with purchase_price: {total}")

        updated = 0
        skipped = 0
        sample: list[str] = []

        offset = 0
        while offset < total:
            batch = list(qs.prefetch_related("categories")[offset : offset + chunk])
            offset += chunk

            to_update: list[tuple[int, Decimal, Decimal | None]] = []

            for p in batch:
                cat_ids = list(p.categories.values_list("pk", flat=True))

                # Determine the retail base:
                # Under old (broken) logic: price == purchase_price, old_price == retail.
                # If old_price > purchase_price → old_price is Brain's retail.
                # Otherwise we only have wholesale — apply markup on it.
                if p.old_price and p.old_price > (p.purchase_price or Decimal("0")):
                    base = p.old_price
                else:
                    base = p.purchase_price  # type: ignore[assignment]

                new_price = apply_markup(base, p.brand_id, cat_ids)
                # After applying markup on retail, old_price should be None
                # (we already sell above Brain's retail — no fake discount needed).
                new_old_price: Decimal | None = None

                if new_price == p.price and new_old_price == p.old_price:
                    skipped += 1
                    continue

                to_update.append((p.pk, new_price, new_old_price))

                if len(sample) < 5:
                    sample.append(
                        f"  {p.pk}: {p.price} → {new_price} "
                        f"(base={base}, old_price: {p.old_price} → {new_old_price})"
                    )

            if to_update and not dry_run:
                from django.db import connection

                with connection.cursor() as cur:
                    for pk, price, op in to_update:
                        cur.execute(
                            "UPDATE catalog_product SET price=%s, old_price=%s WHERE id=%s",
                            [price, op, pk],
                        )
                updated += len(to_update)
            elif dry_run:
                updated += len(to_update)

        self.stdout.write(f"\nЗміни:")
        for s in sample:
            self.stdout.write(s)
        if len(sample) == 5:
            self.stdout.write("  ... (showing first 5)")

        self.stdout.write(f"\nРезультат:")
        self.stdout.write(f"  Буде/було оновлено: {updated}")
        self.stdout.write(f"  Без змін (вже правильні): {skipped}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY RUN] Нічого не записано. Передайте --confirm."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nГотово. Оновлено {updated} товарів."))
            logger.info("recalculate_brain_prices: updated=%d skipped=%d", updated, skipped)
