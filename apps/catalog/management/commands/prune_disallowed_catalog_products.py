"""
Delete catalog products outside the allowed category whitelist.

KEEPS:
  - every Kancmaster product (source=kancmaster), full feed as-is
  - any product linked to a category inside one of the allowed top-level subtrees
    (same slugs as BRAIN_ALLOWED_CATEGORY_SLUGS / Brain sync whitelist)

DELETES:
  - Brain / manual / legacy products not in those subtrees (incl. no category)

Always run --dry-run first.

Usage:
    python manage.py prune_disallowed_catalog_products --dry-run
    python manage.py prune_disallowed_catalog_products --confirm
    python manage.py prune_disallowed_catalog_products --confirm --batch-size 500
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection, transaction

logger = logging.getLogger(__name__)

_DEFAULT_BATCH = 500


class Command(BaseCommand):
    help = (
        "Видалити товари поза дозволеними категоріями; залишити Kancmaster і 8 гілок Brain whitelist"
    )

    def add_arguments(self, parser: CommandParser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--dry-run",
            action="store_true",
            help="Лише статистика — нічого не видаляти.",
        )
        group.add_argument(
            "--confirm",
            action="store_true",
            help="Підтвердити видалення (НАЗАВЖДИ).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=_DEFAULT_BATCH,
            help=f"Скільки товарів видаляти за одну транзакцію (default {_DEFAULT_BATCH}).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.catalog.models import Category, Product
        from apps.integrations.brain.category_filter import (
            catalog_products_to_keep_queryset,
            catalog_products_to_prune_queryset,
            get_brain_allowed_category_slugs,
        )
        from apps.orders.models import OrderItem

        dry_run: bool = options["dry_run"]
        batch_size: int = max(50, int(options["batch_size"]))

        self._validate_allowed_categories(Category, get_brain_allowed_category_slugs())

        total_all = Product.objects.count()
        keep_qs = catalog_products_to_keep_queryset()
        prune_qs = catalog_products_to_prune_queryset()

        keep_count = keep_qs.count()
        prune_count = prune_qs.count()

        self.stdout.write("\n[prune_disallowed_catalog_products]")
        self.stdout.write(f"  dry_run={dry_run}, batch_size={batch_size}")
        self.stdout.write(f"  Усього товарів у БД:     {total_all}")
        self.stdout.write(self.style.SUCCESS(f"  Залишиться:              {keep_count}"))
        self.stdout.write(self.style.WARNING(f"  Буде видалено:           {prune_count}"))

        self._print_keep_breakdown(Product, keep_qs)
        self._print_prune_breakdown(Product, prune_qs)
        self._print_order_impact(OrderItem, prune_qs)

        if prune_count == 0:
            self.stdout.write(self.style.SUCCESS("\nНічого видаляти."))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n[DRY RUN] Нічого не видалено. Для реального видалення: --confirm"
                ),
            )
            return

        self.stdout.write(self.style.WARNING(f"\nВидаляємо {prune_count} товарів батчами по {batch_size}..."))

        deleted_products = 0
        deleted_rows = 0
        breakdown_total: dict[str, int] = {}

        while True:
            batch_pks = list(prune_qs.values_list("pk", flat=True)[:batch_size])
            if not batch_pks:
                break
            with transaction.atomic():
                batch_deleted, breakdown = Product.objects.filter(pk__in=batch_pks).delete()
            deleted_products += len(batch_pks)
            deleted_rows += batch_deleted
            for label, count in breakdown.items():
                breakdown_total[label] = breakdown_total.get(label, 0) + count
            if deleted_products % (batch_size * 10) == 0 or len(batch_pks) < batch_size:
                self.stdout.write(f"  … {deleted_products}/{prune_count}")

        self.stdout.write(self.style.SUCCESS(f"\nВидалено товарів: {deleted_products}"))
        self.stdout.write(f"Усього записів БД (з каскадами): {deleted_rows}")
        for label, count in sorted(breakdown_total.items()):
            self.stdout.write(f"  {label}: {count}")

        self._post_cleanup()

        logger.info(
            "prune_disallowed_catalog_products: deleted_products=%d deleted_rows=%d breakdown=%s",
            deleted_products,
            deleted_rows,
            breakdown_total,
        )
        self.stdout.write(self.style.SUCCESS("\nГотово. Рекомендується перевірити TTFB великих категорій."))

    def _validate_allowed_categories(self, Category: type, slugs: tuple[str, ...]) -> None:
        missing = [
            slug
            for slug in slugs
            if not Category.objects.filter(slug=slug, is_active=True).exists()
        ]
        if missing:
            raise CommandError(
                "Не знайдено активних категорій для slug: "
                + ", ".join(missing)
                + ". Виправте BRAIN_ALLOWED_CATEGORY_SLUGS або каталог перед видаленням.",
            )

    def _print_keep_breakdown(self, Product: type, keep_qs) -> None:
        self.stdout.write("\n  Залишиться (розбивка):")
        self.stdout.write(
            f"    Kancmaster (усі):           "
            f"{keep_qs.filter(source=Product.SOURCE_KANCMASTER).count():>7}",
        )
        self.stdout.write(
            f"    Brain у дозволених гілках:  "
            f"{keep_qs.filter(source=Product.SOURCE_BRAIN).count():>7}",
        )
        self.stdout.write(
            f"    Manual у дозволених гілках: "
            f"{keep_qs.filter(source=Product.SOURCE_MANUAL).count():>7}",
        )

    def _print_prune_breakdown(self, Product: type, prune_qs) -> None:
        self.stdout.write("\n  Видалиться (розбивка):")
        self.stdout.write(
            f"    Brain поза whitelist:       "
            f"{prune_qs.filter(source=Product.SOURCE_BRAIN).count():>7}",
        )
        self.stdout.write(
            f"    Manual поза whitelist:      "
            f"{prune_qs.filter(source=Product.SOURCE_MANUAL).count():>7}",
        )
        self.stdout.write(
            f"    Kancmaster (має бути 0):    "
            f"{prune_qs.filter(source=Product.SOURCE_KANCMASTER).count():>7}",
        )
        from django.db.models import Count

        no_cat = prune_qs.annotate(_cat_n=Count("categories")).filter(_cat_n=0).count()
        self.stdout.write(
            f"    Без жодної категорії:       {no_cat:>7}",
        )

    def _print_order_impact(self, OrderItem: type, prune_qs) -> None:
        order_lines = OrderItem.objects.filter(product__in=prune_qs).count()
        distinct_orders = (
            OrderItem.objects.filter(product__in=prune_qs).values("order_id").distinct().count()
        )
        self.stdout.write("\n  Історія замовлень:")
        self.stdout.write(f"    Позицій з цими товарами:    {order_lines}")
        self.stdout.write(
            f"    Замовлень (product→NULL):   {distinct_orders}  "
            "(назва/ціна в рядку збережуться)",
        )

    def _post_cleanup(self) -> None:
        from apps.catalog.nav import invalidate_nav_cache

        invalidate_nav_cache()
        self.stdout.write("  Кеш навігації інвалідовано.")

        with connection.cursor() as cursor:
            cursor.execute("ANALYZE catalog_product")
            cursor.execute("ANALYZE catalog_product_categories")
        self.stdout.write("  ANALYZE catalog_product, catalog_product_categories — виконано.")
