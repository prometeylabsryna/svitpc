"""Tests for LiqPay webhook signature + Google/Apple Pay paytype."""

import base64
import hashlib
import json
import pytest
from decimal import Decimal
from unittest.mock import MagicMock


def _make_payload(private_key: str, order_id: str, status: str = "success") -> dict:
    data = base64.b64encode(json.dumps({
        "order_id": order_id,
        "status": status,
        "amount": "100.00",
        "transaction_id": "txn_001",
    }).encode()).decode()
    raw = private_key + data + private_key
    signature = base64.b64encode(hashlib.sha1(raw.encode()).digest()).decode()
    return {"data": data, "signature": signature}


@pytest.mark.django_db
def test_liqpay_valid_webhook(settings, db):
    settings.LIQPAY_PUBLIC_KEY = "pub_key"
    settings.LIQPAY_PRIVATE_KEY = "priv_key"
    settings.SITE_URL = "http://localhost"

    from apps.customers.models import Customer
    from apps.orders.models import Order, OrderStatus

    status = OrderStatus.objects.create(name="Оплачено", is_completed=False)
    customer = Customer.objects.create_user(email="pay@test.ua", password="pass")
    order = Order.objects.create(
        customer=customer, first_name="A", last_name="B",
        phone="+380", email="pay@test.ua",
        total=Decimal("100.00"),
        status=status,
    )

    from apps.integrations.payments.liqpay import LiqPayProvider
    provider = LiqPayProvider()
    payload = _make_payload("priv_key", str(order.pk))
    provider.handle_webhook(payload)
    order.refresh_from_db()
    assert order.is_paid is True


@pytest.mark.django_db
def test_liqpay_invalid_signature(settings):
    settings.LIQPAY_PUBLIC_KEY = "pub_key"
    settings.LIQPAY_PRIVATE_KEY = "priv_key"

    from apps.integrations.payments.liqpay import LiqPayProvider
    provider = LiqPayProvider()
    payload = {"data": "bad_data", "signature": "bad_sig"}
    provider.handle_webhook(payload)  # should not raise


@pytest.mark.django_db
def test_liqpay_paytype_google_pay(settings):
    settings.LIQPAY_PUBLIC_KEY = "pub_key"
    settings.LIQPAY_PRIVATE_KEY = "priv_key"
    settings.SITE_URL = "http://localhost"

    from apps.integrations.payments.liqpay import LiqPayProvider
    provider = LiqPayProvider()
    order = MagicMock()
    order.total = Decimal("500.00")
    order.pk = 1
    order.payment_method = "google_pay"
    result = provider.create_payment(order)
    data_decoded = json.loads(base64.b64decode(result["data"]).decode())
    assert data_decoded["paytype"] == "gpay"


@pytest.mark.django_db
def test_liqpay_paytype_apple_pay(settings):
    settings.LIQPAY_PUBLIC_KEY = "pub_key"
    settings.LIQPAY_PRIVATE_KEY = "priv_key"
    settings.SITE_URL = "http://localhost"

    from apps.integrations.payments.liqpay import LiqPayProvider
    provider = LiqPayProvider()
    order = MagicMock()
    order.total = Decimal("500.00")
    order.pk = 2
    order.payment_method = "apple_pay"
    result = provider.create_payment(order)
    data_decoded = json.loads(base64.b64decode(result["data"]).decode())
    assert data_decoded["paytype"] == "apay"
