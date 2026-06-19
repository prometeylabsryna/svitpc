"""Backfill descriptions and characteristics for Brain products.

Fetches /product/{pid} and /product_options/{pid} from Brain API
for products that are missing description or attributes.

Brain API rate limit: ~3 req/sec → 1346 products ≈ 8 min.

Usage:
    python manage.py backfill_brain_descriptions --dry-run
    python manage.py backfill_brain_descriptions           # all missing desc
    python manage.py backfill_brain_descriptions --all     # all Brain products
    python manage.py backfill_brain_descriptions --limit 100
"""

from __future__ import annotations

import logging
import time
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Завантажити описи та характеристики для Brain-товарів з API"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--all",
            action="store_true",
            help="Оновити всі Brain-товари (не тільки без опису)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Обмежити кількість товарів (0 = без обмеження)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показати кількість, нічого не змінювати",
        )
        parser.add_argument(
            "--skip-options",
            action="store_true",
            help="Не синхронізувати характеристики (тільки опис)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.catalog.models import Product
        from apps.integrations.brain.client import BrainAPIClient
        from apps.integrations.brain.services import (
            apply_detail_to_product,
            build_category_map_from_db,
            sync_product_options,
        )

        dry_run: bool = options["dry_run"]
        update_all: bool = options["all"]
        limit: int = options["limit"]
        skip_options: bool = options["skip_options"]

        qs = Product.objects.filter(
            source=Product.SOURCE_BRAIN,
            external_id__gt="",
        ).order_by("pk")

        if not update_all:
            qs = qs.filter(description="")

        if limit:
            qs = qs[:limit]

        total = qs.count() if not limit else min(qs.count(), limit)
        self.stdout.write(
            f"[backfill_brain_descriptions] total={total} "
            f"dry_run={dry_run} all={update_all} skip_options={skip_options}"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING(f"[DRY RUN] Буде оброблено {total} товарів. Запусти без --dry-run."))
            return

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Всі Brain-товари вже мають описи."))
            return

        client = BrainAPIClient()
        vendor_map = client.get_all_vendors()
        cat_map = build_category_map_from_db(client)

        updated = 0
        failed = 0
        t0 = time.time()

        products = list(qs.only("pk", "external_id", "name", "description"))

        for i, product in enumerate(products, 1):
            try:
                brain_id = int(product.external_id)
            except (ValueError, TypeError):
                failed += 1
                continue

            try:
                detail = client.get_product(brain_id, lang="ua")
            except Exception as exc:
                logger.warning("Brain get_product(%d) failed: %s", brain_id, exc)
                failed += 1
                continue

            if not detail:
                failed += 1
                continue

            changed = apply_detail_to_product(
                product,
                detail,
                vendor_map=vendor_map,
                cat_map=cat_map,
                update_price=False,
                update_stock=False,
                update_brand=False,
                update_category=False,
                update_image=False,
            )

            if not skip_options:
                try:
                    sync_product_options(client, product, brain_id)
                except Exception as exc:
                    logger.warning("sync_product_options(%d) failed: %s", brain_id, exc)

            if changed or not skip_options:
                updated += 1

            if i % 50 == 0:
                elapsed = time.time() - t0
                rate = i / elapsed
                eta = (total - i) / rate if rate > 0 else 0
                self.stdout.write(
                    f"  {i}/{total} | оновлено={updated} | помилок={failed} | "
                    f"ETA={eta:.0f}с"
                )

        elapsed = time.time() - t0
        self.stdout.write(
            self.style.SUCCESS(
                f"\nГотово за {elapsed:.0f}с. "
                f"Оновлено: {updated} | Помилок: {failed}"
            )
        )
        logger.info(
            "backfill_brain_descriptions: updated=%d failed=%d elapsed=%.0fs",
            updated, failed, elapsed,
        )
