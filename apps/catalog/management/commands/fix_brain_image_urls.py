"""Fix Brain image URLs: convert old apiplus/... format to static/images/prod_img/X/Y/...

Case 1 (with folder):  apiplus/58/U0449958_big.jpg   → static/images/prod_img/5/8/U0449958_big.jpg
Case 2 (empty folder): apiplus//U0321950_main.jpg    → static/images/prod_img/5/0/U0321950_main.jpg
                       Folder digits are derived from the last two digits of the product code.
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Fix Brain product image URLs (apiplus → static/images/prod_img)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show counts without modifying data")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        tables = ["catalog_product", "catalog_productimage"]

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM catalog_product WHERE image_url LIKE %s", ["https://opt.brain.com.ua/apiplus/%"])
            p1 = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM catalog_productimage WHERE image_url LIKE %s", ["https://opt.brain.com.ua/apiplus/%"])
            p2 = cursor.fetchone()[0]

        self.stdout.write(f"Products to fix: {p1}")
        self.stdout.write(f"ProductImages to fix: {p2}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        # Case 1: apiplus/XY/filename  →  static/images/prod_img/X/Y/filename
        sql_with_folder = """
            UPDATE {table}
            SET image_url = regexp_replace(
                image_url,
                'https://opt\\.brain\\.com\\.ua/apiplus/([0-9])([0-9])/(.+)',
                'https://opt.brain.com.ua/static/images/prod_img/\\1/\\2/\\3'
            )
            WHERE image_url LIKE 'https://opt.brain.com.ua/apiplus/_%/%'
        """

        # Case 2: apiplus//CODE_suffix  →  static/images/prod_img/X/Y/CODE_suffix
        # Extract X/Y from last two digits of the product code (before the underscore).
        sql_empty_folder = """
            UPDATE {table}
            SET image_url = regexp_replace(
                image_url,
                'https://opt\\.brain\\.com\\.ua/apiplus//([A-Za-z][0-9]*)([0-9])([0-9])(_.*)',
                'https://opt.brain.com.ua/static/images/prod_img/\\2/\\3/\\1\\2\\3\\4'
            )
            WHERE image_url LIKE 'https://opt.brain.com.ua/apiplus//%'
        """

        total_products = total_images = 0
        with connection.cursor() as cursor:
            for table in tables:
                cursor.execute(sql_with_folder.format(table=table))
                n = cursor.rowcount
                cursor.execute(sql_empty_folder.format(table=table))
                n += cursor.rowcount
                if table == "catalog_product":
                    total_products = n
                else:
                    total_images = n

        self.stdout.write(self.style.SUCCESS(f"Updated {total_products} products, {total_images} product images."))
