"""Tests for notification dispatch helpers."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest


@pytest.mark.django_db
def test_notify_order_customer_all_channels(customer_factory):
    from decimal import Decimal

    from apps.notifications.dispatch import notify_order_customer
    from apps.orders.models import Order, OrderStatus

    customer = customer_factory(
        telegram_chat_id="12345",
        viber_id="viber-user-1",
        consent_sms=True,
        phone="+380501234567",
    )
    status = OrderStatus.objects.create(name="Новий", notify_customer=True)
    order = Order.objects.create(
        customer=customer,
        status=status,
        first_name="Test",
        last_name="User",
        email="buyer@test.com",
        phone="+380501234567",
        total=Decimal("1000.00"),
    )

    with patch("apps.notifications.dispatch.send_notification") as mock_send:
        notify_order_customer(
            order,
            "order_status_changed",
            push_title="Title",
            push_body="Body",
        )

    channels = [call.args[0] for call in mock_send.call_args_list]
    assert channels == ["email", "sms", "telegram", "viber", "push"]


@pytest.mark.django_db
def test_notify_customer_channels(customer_factory):
    from apps.notifications.dispatch import notify_customer_channels

    customer = customer_factory(
        consent_email=True,
        consent_sms=True,
        telegram_chat_id="99",
        viber_id="viber-99",
        phone="+380501234567",
    )
    ctx = {"customer": customer, "bonus_amount": 100}

    with patch("apps.notifications.dispatch.send_notification") as mock_send:
        notify_customer_channels(customer, "birthday_greeting", ctx)

    assert mock_send.call_count == 4


@pytest.mark.django_db
def test_apply_bonus_adjustment(customer_factory):
    from apps.loyalty.models import BonusTransaction
    from apps.loyalty.services import apply_bonus_adjustment

    customer = customer_factory(bonus_balance=Decimal("50.00"))
    tx = apply_bonus_adjustment(customer, Decimal("25.50"), "Тестове нарахування")

    customer.refresh_from_db()
    assert customer.bonus_balance == Decimal("75.50")
    assert tx.transaction_type == BonusTransaction.TYPE_ADJUST
    assert tx.amount == Decimal("25.50")
    assert tx.balance_after == Decimal("75.50")


@pytest.mark.django_db
def test_apply_bonus_adjustment_negative_balance_raises(customer_factory):
    from apps.loyalty.services import LoyaltyError, apply_bonus_adjustment

    customer = customer_factory(bonus_balance=Decimal("10.00"))
    with pytest.raises(LoyaltyError):
        apply_bonus_adjustment(customer, Decimal("-20.00"))
