from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import httpx
from django.test import TestCase, override_settings

from apps.integrations.vchasnokasa.client import VchasnoKasaClient
from apps.orders.models import Order, OrderItem, OrderStatus


@override_settings(
    VCHASNO_CASHBOX_KEY="test-token",
    VCHASNO_DEVICE_NAME="SvitPC-test",
    VCHASNO_TAX_GRP=1,
)
class VchasnoKasaClientTests(TestCase):
    def setUp(self) -> None:
        self.status = OrderStatus.objects.create(name="Новий")
        self.order = Order.objects.create(
            status=self.status,
            first_name="Test",
            last_name="User",
            email="test@example.com",
            phone="+380501234567",
            payment_method="card",
            total=Decimal("900.00"),
            delivery_cost=Decimal("100.00"),
        )
        OrderItem.objects.create(
            order=self.order,
            name="Товар 1",
            sku="SKU1",
            price=Decimal("500.00"),
            qty=2,
        )

    def test_not_configured_without_token(self) -> None:
        with override_settings(VCHASNO_CASHBOX_KEY=""):
            client = VchasnoKasaClient()
            self.assertFalse(client.is_configured())
            self.assertIsNone(client.create_receipt(self.order))

    def _mock_response(self, payload: dict, status_code: int = 200) -> httpx.Response:
        return httpx.Response(
            status_code,
            json=payload,
            request=httpx.Request("POST", "https://kasa.vchasno.ua/api/v2/fiscal/execute"),
        )

    def test_create_receipt_success(self) -> None:
        mock_resp = self._mock_response(
            {
                "res": 0,
                "info": {"qr": "https://kasa.vchasno.ua/c/TEST_check?id=TEST_check"},
            }
        )
        client = VchasnoKasaClient()
        with patch.object(httpx, "post", return_value=mock_resp) as mock_post:
            url = client.create_receipt(self.order)

        self.assertEqual(url, "https://kasa.vchasno.ua/c/TEST_check?id=TEST_check")
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        receipt = payload["fiscal"]["receipt"]
        self.assertEqual(receipt["sum"], 1000.0)
        self.assertEqual(receipt["pays"], [{"type": 1, "sum": 1000.0}])
        self.assertEqual(len(receipt["rows"]), 2)
        self.assertEqual(receipt["rows"][0]["disc"], 100.0)
        self.assertEqual(mock_post.call_args.kwargs["headers"]["Authorization"], "test-token")

    def test_create_receipt_cod_uses_cash_payment(self) -> None:
        self.order.payment_method = "cod"
        self.order.save(update_fields=["payment_method"])
        mock_resp = self._mock_response({"res": 0, "info": {"qr": "https://example.com/check"}})
        client = VchasnoKasaClient()
        with patch.object(httpx, "post", return_value=mock_resp) as mock_post:
            client.create_receipt(self.order)

        pays = mock_post.call_args.kwargs["json"]["fiscal"]["receipt"]["pays"]
        self.assertEqual(pays[0]["type"], 0)

    def test_create_receipt_api_error(self) -> None:
        mock_resp = self._mock_response({"res": 1001, "errortxt": "bad request"})
        client = VchasnoKasaClient()
        with patch.object(httpx, "post", return_value=mock_resp):
            self.assertIsNone(client.create_receipt(self.order))

    def test_ping_success(self) -> None:
        mock_resp = self._mock_response({"res": 0})
        client = VchasnoKasaClient()
        with patch.object(httpx, "post", return_value=mock_resp):
            self.assertTrue(client.ping())
