"""
Backfill ProductFilter facets (діагональ/CPU/RAM/відеокарта/SSD/колір) from
уже синхронізованих ProductAttribute — без жодних запитів до Brain/Kancmaster API.

Потрібен один раз після деплою `apps/catalog/derived_filters.py`, щоб товари,
синхронізовані ДО цієї зміни, отримали фасети в сайдбарі каталогу. Надалі
нові товари отримують фасети автоматично під час синку (content_sync.py,
kancmaster/attributes.py).

Ідемпотентна — безпечно запускати повторно (get_or_create всередині).

НІКОЛИ не падає на середині 125k+ товарів: dedupe запускається заздалегідь,
кожен товар обробляється в окремому savepoint — помилка одного товару
логується й пропускається, решта батчу й наступні батчі виконуються далі.

Usage:
    python3 manage.py backfill_derived_filters
    python3 manage.py backfill_derived_filters --batch-size 1000
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

logger = logging.getLogger(__name__)

_DEFAULT_BATCH = 1000
_MAX_FAILED_PKS_SHOWN = 30


class Command(BaseCommand):
    help = "Наповнити ProductFilter (діагональ/CPU/RAM/відеокарта/SSD/колір) з ProductAttribute."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--batch-size",
            type=int,
            default=_DEFAULT_BATCH,
            help=f"Товарів на одну транзакцію (default {_DEFAULT_BATCH}).",
        )
        parser.add_argument(
            "--skip-dedupe",
            action="store_true",
            help="Не запускати dedupe_catalog_filters перед бекфілом (за замовчуванням запускається).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.catalog.derived_filters import sync_derived_filters_for_product
        from apps.catalog.models import Product

        batch_size: int = max(50, int(options["batch_size"]))

        if not options["skip_dedupe"]:
            self._dedupe_filters_first()

        base_qs = Product.objects.filter(attributes__isnull=False).distinct().order_by("pk")
        total = base_qs.count()
        self.stdout.write(f"\n[backfill_derived_filters] товарів з характеристиками: {total}")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Нічого обробляти."))
            return

        processed = 0
        created_total = 0
        failed_pks: list[int] = []
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
                    try:
                        with transaction.atomic():  # savepoint — ізолює збій одного товару
                            created_total += sync_derived_filters_for_product(product)
                    except Exception:
                        failed_pks.append(product.pk)
                        logger.exception(
                            "backfill_derived_filters: товар pk=%s не вдалося обробити",
                            product.pk,
                        )

            processed += len(batch)
            last_pk = batch[-1].pk
            suffix = f", збоїв: {len(failed_pks)}" if failed_pks else ""
            self.stdout.write(
                f"  … {processed}/{total} обробено, нових зв'язків: {created_total}{suffix}",
            )

        self._invalidate_caches()
        self._report_result(processed, created_total, failed_pks)

    def _dedupe_filters_first(self) -> None:
        from apps.catalog.filter_dedup import dedupe_catalog_filters

        self.stdout.write("[backfill_derived_filters] dedupe_catalog_filters...")
        stats = dedupe_catalog_filters()
        self.stdout.write(
            f"  груп злито: {stats.groups_merged}, фільтрів злито: {stats.filters_merged}, "
            f"фільтрів переміщено: {stats.filters_moved}",
        )

    def _report_result(self, processed: int, created_total: int, failed_pks: list[int]) -> None:
        if failed_pks:
            shown = failed_pks[:_MAX_FAILED_PKS_SHOWN]
            more = f" (+{len(failed_pks) - _MAX_FAILED_PKS_SHOWN} ще)" if len(failed_pks) > _MAX_FAILED_PKS_SHOWN else ""
            self.stdout.write(
                self.style.WARNING(
                    f"\nЗбоїв: {len(failed_pks)} товарів — pk: {shown}{more}. "
                    "Деталі у логах (logger.exception). Команда ідемпотентна — можна перезапустити.",
                ),
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"\nГотово. Товарів обробено: {processed}, нових ProductFilter: {created_total}, "
                f"збоїв: {len(failed_pks)}",
            ),
        )

    def _invalidate_caches(self) -> None:
        from apps.catalog.cache_invalidation import invalidate_catalog_listing_caches

        # rewarm=True (default) — одразу ставить прогрів топ-категорій у чергу,
        # реальний відвідувач не платить за холодні фасети з новими даними.
        invalidate_catalog_listing_caches()
        self.stdout.write("  Кеші фасетів/лічильників інвалідовано, прогрів поставлено в черзу.")
