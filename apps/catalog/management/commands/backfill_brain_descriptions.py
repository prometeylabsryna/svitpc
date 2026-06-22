"""Backfill descriptions and characteristics for Brain products.

Uses POST /products/content/{SID} (OWN_MODE) — full descriptions in batches.

Usage:
    python manage.py backfill_brain_descriptions --dry-run
    python manage.py backfill_brain_descriptions           # products without description_uk
    python manage.py backfill_brain_descriptions --all     # all Brain products
    python manage.py backfill_brain_descriptions --limit 100
"""

from __future__ import annotations

import logging
import time
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

logger = logging.getLogger(__name__)

_PROCESS_CHUNK = 500


class Command(BaseCommand):
    help = "Завантажити описи та характеристики для Brain-товарів (products/content API)"

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
        from apps.integrations.brain.content_sync import backfill_descriptions_from_content

        dry_run: bool = options["dry_run"]
        update_all: bool = options["all"]
        limit: int = options["limit"]
        skip_options: bool = options["skip_options"]

        qs = Product.objects.filter(
            source=Product.SOURCE_BRAIN,
            external_id__gt="",
        ).order_by("pk")

        if not update_all:
            qs = qs.filter(description_uk="")

        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(
            f"[backfill_brain_descriptions] total={total} "
            f"dry_run={dry_run} all={update_all} skip_options={skip_options}"
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"[DRY RUN] Буде оброблено {total} товарів. Запусти без --dry-run.")
            )
            return

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Всі Brain-товари вже мають описи."))
            return

        client = BrainAPIClient()
        updated = 0
        no_desc = 0
        api_miss = 0
        failed_ids = 0
        t0 = time.time()
        processed = 0

        products = list(qs.only("pk", "external_id", "name", "description_uk"))

        for offset in range(0, len(products), _PROCESS_CHUNK):
            chunk = products[offset : offset + _PROCESS_CHUNK]
            product_map: dict[int, Product] = {}
            for product in chunk:
                try:
                    brain_id = int(product.external_id)
                except (ValueError, TypeError):
                    failed_ids += 1
                    continue
                if brain_id > 0:
                    product_map[brain_id] = product

            u, nd, miss = backfill_descriptions_from_content(
                client,
                product_map,
                skip_options=skip_options,
            )
            updated += u
            no_desc += nd
            api_miss += miss
            processed += len(chunk)

            elapsed = time.time() - t0
            rate = processed / elapsed if elapsed > 0 else 0
            eta = (total - processed) / rate if rate > 0 else 0
            self.stdout.write(
                f"  {processed}/{total} | оновлено={updated} | без опису в API={no_desc} | "
                f"пропущено API={api_miss} | ETA={eta:.0f}с"
            )

        elapsed = time.time() - t0
        self.stdout.write(
            self.style.SUCCESS(
                f"\nГотово за {elapsed:.0f}с. "
                f"Оновлено: {updated} | Без опису в Brain: {no_desc} | "
                f"Немає в відповіді API: {api_miss} | Невалідні ID: {failed_ids}"
            )
        )
        logger.info(
            "backfill_brain_descriptions: updated=%d no_desc=%d api_miss=%d failed_ids=%d elapsed=%.0fs",
            updated,
            no_desc,
            api_miss,
            failed_ids,
            elapsed,
        )
