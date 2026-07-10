"""
Backfill ProductFilter facets (діагональ/CPU/RAM/відеокарта/SSD/колір) from
уже синхронізованих ProductAttribute — без жодних запитів до Brain/Kancmaster API.

Потрібен один раз після деплою `apps/catalog/derived_filters.py`, щоб товари,
синхронізовані ДО цієї зміни, отримали фасети в сайдбарі каталогу. Надалі
нові товари отримують фасети автоматично під час синку (content_sync.py,
kancmaster/attributes.py).

Ідемпотентна — безпечно запускати повторно (get_or_create всередині).

Usage:
    python3 manage.py backfill_derived_filters
    python3 manage.py backfill_derived_filters --batch-size 1000
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

_DEFAULT_BATCH = 1000


class Command(BaseCommand):
    help = "Наповнити ProductFilter (діагональ/CPU/RAM/відеокарта/SSD/колір) з ProductAttribute."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--batch-size",
            type=int,
            default=_DEFAULT_BATCH,
            help=f"Товарів на одну транзакцію (default {_DEFAULT_BATCH}).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.catalog.derived_filters import sync_derived_filters_for_product
        from apps.catalog.models import Product

        batch_size: int = max(50, int(options["batch_size"]))

        base_qs = Product.objects.filter(attributes__isnull=False).distinct().order_by("pk")
        total = base_qs.count()
        self.stdout.write(f"\n[backfill_derived_filters] товарів з характеристиками: {total}")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Нічого обробляти."))
            return

        processed = 0
        created_total = 0
        last_pk = 0

        while True:
            batch = list(
                base_qs.filter(pk__gt=last_pk)
                .prefetch_related("attributes__attribute")[:batch_size],
            )
            if not batch:
                break

            with transaction.atomic():
                for product in batch:
                    created_total += sync_derived_filters_for_product(product)

            processed += len(batch)
            last_pk = batch[-1].pk
            self.stdout.write(f"  … {processed}/{total} обробено, нових зв'язків: {created_total}")

        self._invalidate_caches()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nГотово. Товарів обробено: {processed}, нових ProductFilter: {created_total}",
            ),
        )

    def _invalidate_caches(self) -> None:
        from apps.catalog.cache_invalidation import invalidate_catalog_listing_caches

        invalidate_catalog_listing_caches()
        self.stdout.write("  Кеші фасетів/лічильників інвалідовано.")
