"""Ідемпотентність webhook-ів оплати: дубль події = один Payment, один is_paid."""

import base64
import hashlib
import hmac
import json
from decimal import Decimal

import pytest

from apps.payments.models import Payment


@pytest.fixture
def order(customer_factory):
    from apps.orders.models import Order, OrderStatus

    status = OrderStatus.objects.create(name="Нове", is_completed=False)
    customer = customer_factory()
    return Order.objects.create(
        customer=customer,
        first_name="Тест",
        last_name="Юзер",
        phone="+380961234567",
        email=customer.email,
        total=Decimal("1500.00"),
        status=status,
    )


def _liqpay_payload(private_key: str, order_id: int, status: str = "success") -> dict:
    data = base64.b64encode(json.dumps({
        "order_id": str(order_id),
        "status": status,
        "amount": "1500.00",
        "payment_id": "777",
    }).encode()).decode()
    raw = private_key + data + private_key
    signature = base64.b64encode(hashlib.sha1(raw.encode()).digest()).decode()
    return {"data": data, "signature": signature}


@pytest.mark.django_db
def test_liqpay_duplicate_webhook_single_payment(settings, order):
    settings.LIQPAY_PUBLIC_KEY = "pub_key"
    settings.LIQPAY_PRIVATE_KEY = "priv_key"
    settings.SITE_URL = "http://localhost"

    from apps.integrations.payments.liqpay import LiqPayProvider

    provider = LiqPayProvider()
    payload = _liqpay_payload("priv_key", order.pk)
    provider.handle_webhook(payload)
    provider.handle_webhook(payload)  # дубль

    order.refresh_from_db()
    assert order.is_paid is True
    assert order.payment_id == "777"
    assert Payment.objects.filter(order=order, provider="liqpay").count() == 1


def _wayforpay_body(secret: str, order_id: int, status: str = "Approved") -> bytes:
    data = {
        "merchantAccount": "test_merchant",
        "orderReference": str(order_id),
        "amount": "1500.00",
        "currency": "UAH",
        "authCode": "AUTH1",
        "cardPan": "44****11",
        "transactionStatus": status,
        "reasonCode": "1100",
        "transactionId": "w4p-42",
    }
    fields = [
        data["merchantAccount"], data["orderReference"], data["amount"],
        data["currency"], data["authCode"], data["cardPan"],
        data["transactionStatus"], data["reasonCode"],
    ]
    message = ";".join(fields)
    data["merchantSignature"] = hmac.new(secret.encode(), message.encode(), hashlib.md5).hexdigest()
    return json.dumps(data).encode()


@pytest.mark.django_db
def test_wayforpay_duplicate_webhook_single_payment(settings, order):
    settings.WAYFORPAY_SECRET_KEY = "w4p_secret"

    from apps.integrations.payments.wayforpay import WayForPayProvider

    provider = WayForPayProvider()
    body = _wayforpay_body("w4p_secret", order.pk)
    provider.handle_webhook(body)
    provider.handle_webhook(body)  # дубль

    order.refresh_from_db()
    assert order.is_paid is True
    assert Payment.objects.filter(order=order, provider="wayforpay").count() == 1


@pytest.mark.django_db
def test_wayforpay_invalid_signature_ignored(settings, order):
    settings.WAYFORPAY_SECRET_KEY = "w4p_secret"

    from apps.integrations.payments.wayforpay import WayForPayProvider

    body = _wayforpay_body("wrong_secret", order.pk)
    WayForPayProvider().handle_webhook(body)

    order.refresh_from_db()
    assert order.is_paid is False
    assert Payment.objects.count() == 0


def _monobank_body(order_id: int, status: str = "success") -> bytes:
    return json.dumps({
        "invoiceId": "inv-123",
        "status": status,
        "reference": str(order_id),
    }).encode()


@pytest.mark.django_db
def test_monobank_duplicate_webhook_single_payment(settings, order):
    settings.MONOBANK_TOKEN = "mono_token"

    from apps.integrations.payments.monobank import MonobankProvider

    provider = MonobankProvider()
    body = _monobank_body(order.pk)
    signature = hmac.new(b"mono_token", body, hashlib.sha256).hexdigest()
    provider.handle_webhook(body, signature=signature)
    provider.handle_webhook(body, signature=signature)  # дубль

    order.refresh_from_db()
    assert order.is_paid is True
    assert order.payment_id == "inv-123"
    assert Payment.objects.filter(order=order, provider="monobank").count() == 1


@pytest.mark.django_db
def test_monobank_processing_status_not_paid(settings, order):
    """Проміжний статус processing не позначає замовлення оплаченим."""
    settings.MONOBANK_TOKEN = "mono_token"

    from apps.integrations.payments.monobank import MonobankProvider

    MonobankProvider().handle_webhook(_monobank_body(order.pk, status="processing"))

    order.refresh_from_db()
    assert order.is_paid is False
    assert Payment.objects.count() == 0


@pytest.mark.django_db
def test_failed_event_recorded_without_paid(settings, order):
    settings.LIQPAY_PUBLIC_KEY = "pub_key"
    settings.LIQPAY_PRIVATE_KEY = "priv_key"

    from apps.integrations.payments.liqpay import LiqPayProvider

    payload = _liqpay_payload("priv_key", order.pk, status="failure")
    LiqPayProvider().handle_webhook(payload)

    order.refresh_from_db()
    assert order.is_paid is False
    pmt = Payment.objects.get(order=order)
    assert pmt.status == Payment.STATUS_FAILED
