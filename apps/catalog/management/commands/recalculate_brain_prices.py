"""Recalculate Brain product prices to match brain.com.ua (no extra markup).

Fetches /product/{id} from Brain API and applies brain_shelf_prices logic.

Usage:
    python manage.py recalculate_brain_prices --dry-run
    python manage.py recalculate_brain_prices --confirm
    python manage.py recalculate_brain_prices --confirm --limit 100
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Перерахувати ціни Brain-товарів = як на brain.com.ua (без додаткової націнки)"

    def add_arguments(self, parser: CommandParser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--dry-run", action="store_true", help="Показати зміни, нічого не писати")
        group.add_argument("--confirm", action="store_true", help="Застосувати зміни")
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Обмежити кількість товарів (0 = усі)",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.35,
            help="Пауза між запитами до Brain API (сек)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.catalog.models import Product
        from apps.integrations.brain.client import BrainAPIClient
        from apps.integrations.brain.services import brain_shelf_prices, brain_stock_from_detail, brain_visibility

        dry_run: bool = options["dry_run"]
        limit: int = options["limit"]
        sleep_s: float = options["sleep"]

        qs = (
            Product.objects.filter(source=Product.SOURCE_BRAIN, external_id__gt="")
            .only("pk", "external_id", "price", "old_price", "purchase_price")
            .order_by("pk")
        )
        if limit:
            qs = qs[:limit]
        total = qs.count()
        self.stdout.write(f"[recalculate_brain_prices] total={total} dry_run={dry_run}")

        client = BrainAPIClient()
        updated = 0
        skipped = 0
        errors = 0
        sample: list[str] = []

        for i, product in enumerate(qs.iterator(chunk_size=100), start=1):
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

            shelf, old_price, wholesale = brain_shelf_prices(detail)
            stock = brain_stock_from_detail(detail)
            hide = product.hide_if_out_of_stock
            visible = brain_visibility(stock, hide)
            if shelf <= 0:
                skipped += 1
                continue

            purchase = wholesale if wholesale > 0 else None
            if (
                product.price == shelf
                and product.old_price == old_price
                and product.purchase_price == purchase
                and product.stock == stock
                and product.is_visible == visible
            ):
                skipped += 1
                continue

            if len(sample) < 5:
                sample.append(
                    f"  {product.external_id}: {product.price} → {shelf}"
                    f" (old: {product.old_price} → {old_price})"
                )

            if not dry_run:
                Product.objects.filter(pk=product.pk).update(
                    price=shelf,
                    old_price=old_price,
                    purchase_price=purchase,
                    stock=stock,
                    is_visible=visible,
                )
            updated += 1

            if sleep_s > 0:
                time.sleep(sleep_s)

            if i % 100 == 0:
                self.stdout.write(f"  {i}/{total} | оновлено={updated} | пропущено={skipped}")

        for line in sample:
            self.stdout.write(line)

        self.stdout.write(f"\nРезультат: оновлено={updated}, пропущено={skipped}, помилок={errors}")
        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY RUN] Нічого не записано."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Готово. Оновлено {updated} товарів."))
