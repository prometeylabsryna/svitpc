from decimal import Decimal
from pathlib import Path

from django.test import TestCase

from apps.services.models import PriceItem, Service, ServiceCategory
from apps.services.price_import import DEFAULT_WORKBOOK, import_service_prices, parse_price_workbook

WORKBOOK = Path(__file__).resolve().parents[3] / DEFAULT_WORKBOOK


class ParsePriceWorkbookTests(TestCase):
    def test_parses_all_categories_and_items(self):
        if not WORKBOOK.exists():
            self.skipTest("Workbook fixture missing")

        categories = parse_price_workbook(WORKBOOK)
        self.assertEqual(len(categories), 7)
        self.assertEqual(sum(len(category.items) for category in categories), 63)

        laptop_category = next(category for category in categories if category.name == "Ноутбуки")
        matrix_row = next(item for item in laptop_category.items if "Матриці" in item.name)
        self.assertEqual(matrix_row.price, Decimal("850"))
        self.assertEqual(matrix_row.unit, "шт")

        marked_rows = [
            item
            for category in categories
            for item in category.items
            if item.excludes_materials
        ]
        self.assertEqual(len(marked_rows), 10)


class ImportServicePricesTests(TestCase):
    def test_import_creates_catalog(self):
        if not WORKBOOK.exists():
            self.skipTest("Workbook fixture missing")

        stats = import_service_prices(WORKBOOK)
        self.assertEqual(stats["categories"], 7)
        self.assertEqual(stats["services"], 7)
        self.assertEqual(stats["price_items"], 63)
        self.assertEqual(ServiceCategory.objects.count(), 7)
        self.assertEqual(Service.objects.filter(is_active=True).count(), 7)
        self.assertEqual(PriceItem.objects.count(), 63)

        laptop_service = Service.objects.get(name="Ремонт ноутбуків")
        self.assertTrue(laptop_service.show_on_home)
        self.assertEqual(laptop_service.name_en, "Laptop repair")
        self.assertTrue(laptop_service.description_en)
        self.assertEqual(laptop_service.prices.count(), 16)
        first_price = laptop_service.prices.order_by("sort_order").first()
        self.assertTrue(first_price.name_en)

    def test_import_is_idempotent(self):
        if not WORKBOOK.exists():
            self.skipTest("Workbook fixture missing")

        import_service_prices(WORKBOOK)
        import_service_prices(WORKBOOK)
        self.assertEqual(PriceItem.objects.count(), 63)
