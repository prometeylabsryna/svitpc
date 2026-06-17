"""
Delete products that were imported from the OpenCart SQL dump,
keeping only products from Brain API and Kancmaster XML syncs.

Usage (ЗАВЖДИ спочатку dry-run):
    python manage.py purge_opencart_products --dry-run
    python manage.py purge_opencart_products --dry-run --mode all-oc
    python manage.py purge_opencart_products --confirm
    python manage.py purge_opencart_products --confirm --mode all-oc

Modes:
    manual-only  (default) — видаляє лише source=manual (прийшли з SQL без Brain ID).
                             Brain-продукти що мають oc_id — залишаються (Brain sync їх оновлює).
    all-oc                 — видаляє ВСЕ з oc_id IS NOT NULL (повне очищення SQL-дампу).
                             Brain sync перестворить Brain-продукти з нуля, Kancmaster збережеться.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

logger = logging.getLogger(__name__)

VALID_MODES = ("manual-only", "all-oc")


class Command(BaseCommand):
    help = "Видалити товари імпортовані з OpenCart SQL; залишити лише Brain API / Kancmaster"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--mode",
            default="manual-only",
            choices=VALID_MODES,
            help=(
                "manual-only: видаляє source=manual+oc_id (безпечно). "
                "all-oc: видаляє ВСЕ з oc_id IS NOT NULL (повне очищення SQL-дампу)."
            ),
        )
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--dry-run",
            action="store_true",
            help="Лише показати кількість — нічого не видаляти.",
        )
        group.add_argument(
            "--confirm",
            action="store_true",
            help="Підтвердити видалення. БЕЗ --dry-run ДАНІ БУДУТЬ ВИДАЛЕНІ НАЗАВЖДИ.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.catalog.models import Product

        mode: str = options["mode"]
        dry_run: bool = options["dry_run"]

        qs = self._build_queryset(Product, mode)
        total = qs.count()

        self.stdout.write(f"\n[purge_opencart_products] mode={mode}, dry_run={dry_run}")
        self.stdout.write(f"Знайдено товарів для видалення: {total}")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Нічого видаляти — операція завершена."))
            return

        self._print_breakdown(Product, mode)

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY RUN] Нічого не видалено. Передайте --confirm для реального видалення."))
            return

        self.stdout.write(self.style.WARNING(f"\nВидаляємо {total} товарів..."))

        with transaction.atomic():
            deleted_count, deleted_per_model = qs.delete()

        self.stdout.write(self.style.SUCCESS(f"Видалено записів: {deleted_count}"))
        for model_label, count in sorted(deleted_per_model.items()):
            self.stdout.write(f"  {model_label}: {count}")

        logger.info(
            "purge_opencart_products: mode=%s deleted=%d breakdown=%s",
            mode,
            deleted_count,
            deleted_per_model,
        )
        self.stdout.write(self.style.SUCCESS("\nГотово. Рекомендується запустити Brain sync та Kancmaster sync."))

    def _build_queryset(self, Product: type, mode: str):
        if mode == "manual-only":
            return Product.objects.filter(
                source=Product.SOURCE_MANUAL,
                oc_id__isnull=False,
            )
        # all-oc: видаляємо всі що мають oc_id (весь SQL-дамп)
        return Product.objects.filter(oc_id__isnull=False)

    def _print_breakdown(self, Product: type, mode: str) -> None:
        brain_oc = Product.objects.filter(source=Product.SOURCE_BRAIN, oc_id__isnull=False).count()
        manual_oc = Product.objects.filter(source=Product.SOURCE_MANUAL, oc_id__isnull=False).count()
        kanc = Product.objects.filter(source=Product.SOURCE_KANCMASTER).count()
        brain_no_oc = Product.objects.filter(source=Product.SOURCE_BRAIN, oc_id__isnull=True).count()
        manual_no_oc = Product.objects.filter(source=Product.SOURCE_MANUAL, oc_id__isnull=True).count()

        self.stdout.write("\nРозбивка товарів у БД:")
        self.stdout.write(f"  Brain API   + oc_id (SQL-мігровані Brain):  {brain_oc:>6}  {'← БУДЕ ВИДАЛЕНО' if mode == 'all-oc' else '← залишається (Brain sync оновлює)'}")
        self.stdout.write(f"  Brain API   без oc_id (чистий Brain sync):  {brain_no_oc:>6}  ← залишається")
        self.stdout.write(f"  Manual      + oc_id (SQL без Brain ID):     {manual_oc:>6}  ← БУДЕ ВИДАЛЕНО")
        self.stdout.write(f"  Manual      без oc_id (вручну):             {manual_no_oc:>6}  ← залишається")
        self.stdout.write(f"  Kancmaster  (завжди без oc_id):             {kanc:>6}  ← залишається")
