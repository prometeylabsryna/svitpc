"""
Set up the "Канцелярські товари" parent category for all Kancmaster subcategories.

Usage:
    python manage.py setup_kancmaster_category
    python manage.py setup_kancmaster_category --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

PARENT_NAME = "Канцелярські товари"
PARENT_SLUG = "kantseliarski-tovary"


class Command(BaseCommand):
    help = "Create 'Канцелярські товари' parent category and move all Kancmaster subcategories under it."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be done without making DB changes.",
        )

    def handle(self, *args, **options):
        from apps.catalog.models import Category, Product

        dry_run: bool = options["dry_run"]

        with transaction.atomic():
            # ── 1. Get or create parent category ─────────────────────────────
            parent, created = Category.objects.get_or_create(
                slug=PARENT_SLUG,
                defaults={
                    "name": PARENT_NAME,
                    "is_active": True,
                    "is_top": True,
                    "sort_order": 50,
                },
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"Created parent category: {PARENT_NAME} (slug={PARENT_SLUG})"))
            else:
                self.stdout.write(f"Parent category already exists: {PARENT_NAME} (pk={parent.pk})")

            # ── 2. Find categories used by Kancmaster products ────────────────
            kanc_cat_ids = set(
                Product.objects.filter(source=Product.SOURCE_KANCMASTER)
                .values_list("categories__id", flat=True)
                .distinct()
            )

            # Also include categories that have a kancmaster_name set
            named_ids = set(
                Category.objects.filter(kancmaster_name__isnull=False)
                .exclude(kancmaster_name="")
                .values_list("id", flat=True)
            )

            target_ids = (kanc_cat_ids | named_ids) - {parent.pk, None}
            target_cats = Category.objects.filter(pk__in=target_ids)

            moved = 0
            skipped = 0
            for cat in target_cats:
                if cat.parent_id == parent.pk:
                    skipped += 1
                    continue
                if dry_run:
                    self.stdout.write(f"  [dry-run] Would move: {cat.name!r} (pk={cat.pk}) → parent={PARENT_NAME}")
                else:
                    cat.parent = parent
                    cat.save(update_fields=["parent"])
                    self.stdout.write(f"  Moved: {cat.name!r} (pk={cat.pk})")
                moved += 1

            if skipped:
                self.stdout.write(f"  Already under parent: {skipped} categories — skipped.")

            # ── 3. Rebuild MPTT tree to fix lft/rght/level/tree_id ────────────
            if not dry_run and moved > 0:
                Category.objects.rebuild()
                self.stdout.write(self.style.SUCCESS("MPTT tree rebuilt."))

            # ── 4. Summary ────────────────────────────────────────────────────
            if dry_run:
                self.stdout.write(self.style.WARNING(f"\n[dry-run] Would move {moved} categories under '{PARENT_NAME}'."))
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nDone. Moved {moved} Kancmaster subcategories under '{PARENT_NAME}'."
                    )
                )

            if dry_run:
                transaction.set_rollback(True)
