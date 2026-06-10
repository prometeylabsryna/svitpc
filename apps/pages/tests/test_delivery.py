from django.test import Client, TestCase
from django.urls import reverse


class DeliveryPageTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.url = reverse("pages:delivery")

    def test_delivery_page_renders(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Доставка замовлень")
        self.assertContains(response, "Нова Пошта")
        self.assertContains(response, "Укрпошта")
        self.assertContains(response, "Самовивіз")

    def test_pickup_address(self) -> None:
        response = self.client.get(self.url)
        self.assertContains(response, "проспект Незалежності, 26")
        self.assertContains(response, "Південноукраїнськ")

    def test_delivery_breadcrumbs(self) -> None:
        response = self.client.get(self.url)
        self.assertContains(response, 'class="breadcrumbs')
        self.assertContains(response, "Головна")
        self.assertContains(response, "Доставка")
