from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from apps.pages.models import ReturnRequest


class ReturnsPageTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.url = reverse("pages:returns")

    def test_returns_page_renders(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Повернення та обмін товару")
        self.assertContains(response, "Заявка на повернення або обмін")
        self.assertContains(response, "Пан Світік підказує")

    def test_returns_breadcrumbs(self) -> None:
        response = self.client.get(self.url)
        self.assertContains(response, 'class="breadcrumbs')
        self.assertContains(response, "Головна")
        self.assertContains(response, "Повернення та обмін товару")
        self.assertNotContains(response, 'breadcrumbs__item">Інформація</span>')

    def test_submit_return_request(self) -> None:
        response = self.client.post(
            self.url,
            {
                "full_name": "Іваненко Іван",
                "order_number": "10001",
                "phone": "+380960763015",
                "reason": ReturnRequest.REASON_RETURN,
                "description": "Товар не підійшов за розміром",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ReturnRequest.objects.count(), 1)
        claim = ReturnRequest.objects.get()
        self.assertEqual(claim.full_name, "Іваненко Іван")
        self.assertEqual(claim.order_number, "10001")

    def test_submit_with_photo(self) -> None:
        # ImageField валідує вміст через Pillow — потрібен справжній JPEG
        import io

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (1, 1), "white").save(buf, format="JPEG")
        photo = SimpleUploadedFile("product.jpg", buf.getvalue(), content_type="image/jpeg")
        response = self.client.post(
            self.url,
            {
                "full_name": "Петренко Петро",
                "order_number": "10002",
                "phone": "+380960763015",
                "reason": ReturnRequest.REASON_WARRANTY,
                "description": "Не вмикається",
                "photo": photo,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        claim = ReturnRequest.objects.get(order_number="10002")
        self.assertTrue(claim.photo.name.endswith(".jpg"))
