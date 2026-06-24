"""Hide visible Brain products that have no retail price."""

from django.core.management.base import BaseCommand

from apps.catalog.models import Product


class Command(BaseCommand):
    help = "Hide Brain products with price <= 0 (delisted / no price from API)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print count only, do not update.",
        )

    def handle(self, *args, **options):
        qs = Product.objects.filter(
            source=Product.SOURCE_BRAIN,
            price__lte=0,
            is_visible=True,
        )
        count = qs.count()
        if options["dry_run"]:
            self.stdout.write(f"Would hide {count} Brain products with zero price.")
            return
        updated = qs.update(is_visible=False)
        self.stdout.write(self.style.SUCCESS(f"Hidden {updated} Brain products with zero price."))
