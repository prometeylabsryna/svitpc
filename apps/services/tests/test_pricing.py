from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from apps.services.models import PriceItem, Service, ServiceCategory
from apps.services.pricing import format_price_item


class PriceFormattingTests(TestCase):
    def setUp(self):
        category = ServiceCategory.objects.create(name="Ремонт", slug="repair")
        self.service = Service.objects.create(
            category=category,
            name="Ремонт ноутбуків",
            slug="laptop-repair",
        )

    def test_price_text_has_priority(self):
        price = PriceItem.objects.create(
            service=self.service,
            name="Діагностика",
            price_text="за домовленістю",
            price_from=Decimal("100.00"),
        )
        self.assertEqual(format_price_item(price), "за домовленістю")

    def test_price_range(self):
        price = PriceItem.objects.create(
            service=self.service,
            name="Заміна матриці",
            price_from=Decimal("1500"),
            price_to=Decimal("3200"),
        )
        self.assertEqual(format_price_item(price), "від 1\u00a0500 ₴ до 3\u00a0200 ₴")

    def test_price_from_only(self):
        price = PriceItem.objects.create(
            service=self.service,
            name="Чистка",
            price_from=Decimal("500"),
        )
        self.assertEqual(format_price_item(price), "від 500 ₴")

    def test_equal_from_and_to(self):
        price = PriceItem.objects.create(
            service=self.service,
            name="Прошивка BIOS",
            price_from=Decimal("300"),
            price_to=Decimal("300"),
        )
        self.assertEqual(format_price_item(price), "300 ₴")


class ServicePricesViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        category = ServiceCategory.objects.create(name="Друк", slug="print")
        self.service = Service.objects.create(
            category=category,
            name="Заправка картриджів",
            slug="cartridge-refill",
            is_active=True,
        )
        PriceItem.objects.create(
            service=self.service,
            name="Ч/б картридж",
            price_from=Decimal("250"),
            sort_order=1,
        )

    def test_prices_page_lists_items(self):
        response = self.client.get(reverse("services:prices"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Прейскурант")
        self.assertContains(response, "Ч/б картридж")
        self.assertContains(response, "250 ₴")


class HomeFeaturedServicesTests(TestCase):
    def test_home_shows_featured_services(self):
        category = ServiceCategory.objects.create(name="Дані", slug="data")
        service = Service.objects.create(
            category=category,
            name="Відновлення даних",
            slug="data-recovery",
            is_active=True,
            show_on_home=True,
        )
        response = Client().get(reverse("catalog:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, service.name)
        self.assertContains(response, service.get_absolute_url())
