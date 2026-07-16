"""
Повністю видалити застарілі кореневі категорії OpenCart разом з товарами.

Категорії "Гаджети (Hi-Tech)" та "Торгівельне обладнання" не входять у список
цільових розділів сайту. Видаляємо ціле MPTT-піддерево (сама категорія +
всі підкатегорії) і всі товари, прив'язані до нього — незалежно від джерела
(Kancmaster/Brain/manual), як і вимагалось.

Always run --dry-run first.

Usage:
    python manage.py remove_legacy_root_categories --dry-run
    python manage.py remove_legacy_root_categories --confirm
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

logger = logging.getLogger(__name__)

LEGACY_ROOT_SLUGS: tuple[str, ...] = (
    "гаджети-hi-tech",
    "торгівельне-обладнання",
)


class Command(BaseCommand):
    help = "Видалити застарілі кореневі категорії (Гаджети, Торгівельне обладнання) і товари в них"

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

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.catalog.models import Category, Product
        from apps.orders.models import OrderItem

        dry_run: bool = options["dry_run"]

        roots = list(Category.objects.filter(slug__in=LEGACY_ROOT_SLUGS))
        found_slugs = {c.slug for c in roots}
        missing = set(LEGACY_ROOT_SLUGS) - found_slugs
        if missing:
            self.stdout.write(
                self.style.WARNING(f"  Вже відсутні (пропускаємо): {', '.join(sorted(missing))}"),
            )
        if not roots:
            self.stdout.write(self.style.SUCCESS("Нічого видаляти — жодної з цих категорій немає в БД."))
            return

        subtree_pks: set[int] = set()
        for root in roots:
            subtree_pks.update(root.get_descendants(include_self=True).values_list("pk", flat=True))

        products_qs = Product.objects.filter(categories__in=subtree_pks).distinct()
        product_count = products_qs.count()

        self.stdout.write("\n[remove_legacy_root_categories]")
        self.stdout.write(f"  dry_run={dry_run}")
        self.stdout.write(f"  Категорій у піддереві (з коренями): {len(subtree_pks)}")
        for root in roots:
            self.stdout.write(f"    - {root.name} ({root.slug}, pk={root.pk})")
        self.stdout.write(self.style.WARNING(f"  Товарів буде видалено: {product_count}"))

        from django.db.models import Count

        by_source = products_qs.values("source").annotate(n=Count("pk")).order_by("-n")
        for row in by_source:
            self.stdout.write(f"    {row['source']}: {row['n']}")

        order_lines = OrderItem.objects.filter(product__in=products_qs).count()
        distinct_orders = OrderItem.objects.filter(product__in=products_qs).values("order_id").distinct().count()
        self.stdout.write("\n  Історія замовлень:")
        self.stdout.write(f"    Позицій з цими товарами: {order_lines}")
        self.stdout.write(
            f"    Замовлень (product→NULL): {distinct_orders}  (назва/ціна в рядку збережуться)",
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n[DRY RUN] Нічого не видалено. Для реального видалення: --confirm"),
            )
            return

        with transaction.atomic():
            deleted_products, _ = products_qs.delete()
            deleted_categories, _ = Category.objects.filter(pk__in=[r.pk for r in roots]).delete()

        self.stdout.write(self.style.SUCCESS(f"\nВидалено товарів: {product_count}"))
        self.stdout.write(self.style.SUCCESS(f"Видалено категорій (з підкатегоріями, каскадом): {deleted_categories}"))

        self._post_cleanup()

        logger.info(
            "remove_legacy_root_categories: slugs=%s deleted_products=%d deleted_category_rows=%d",
            LEGACY_ROOT_SLUGS,
            product_count,
            deleted_categories,
        )
        self.stdout.write(self.style.SUCCESS("\nГотово."))

    def _post_cleanup(self) -> None:
        from apps.catalog.cache_invalidation import invalidate_catalog_listing_caches

        invalidate_catalog_listing_caches()
        self.stdout.write(
            "  Кеші каталогу (nav/home/facets/counts/brands) інвалідовано, прогрів поставлено в черзу.",
        )
