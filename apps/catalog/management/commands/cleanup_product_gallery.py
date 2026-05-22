from django.core.management.base import BaseCommand

from apps.catalog.gallery import cleanup_product_gallery


class Command(BaseCommand):
    help = "Remove stale gallery URLs (_Nmain.jpg) and duplicate ProductImage rows"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report counts only")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        stats = cleanup_product_gallery(dry_run=dry_run)
        for key, val in stats.items():
            self.stdout.write(f"  {key}: {val}")
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
        else:
            self.stdout.write(self.style.SUCCESS("Gallery cleanup complete."))
