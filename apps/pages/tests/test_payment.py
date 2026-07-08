from django.test import Client, TestCase
from django.urls import reverse


class PaymentPageTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.url = reverse("pages:payment")

    def test_payment_page_renders(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Способи оплати")
        self.assertContains(response, "Банківська картка")
        self.assertContains(response, "Google Pay / Apple Pay")
        self.assertContains(response, "Оплата при самовивозі")

    def test_payment_instructions(self) -> None:
        response = self.client.get(self.url)
        self.assertContains(response, "Як оплатити замовлення онлайн")
        self.assertContains(response, "LiqPay")

    def test_payment_breadcrumbs(self) -> None:
        response = self.client.get(self.url)
        self.assertContains(response, 'class="breadcrumbs')
        self.assertContains(response, "Головна")
        self.assertContains(response, "Оплата")

    def test_pickup_maps_link(self) -> None:
        response = self.client.get(self.url)
        self.assertContains(response, "google.com/maps/search/")
        self.assertContains(response, "Відкрити в Google Maps")
