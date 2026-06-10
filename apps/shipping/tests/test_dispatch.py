"""Shipment dispatch tests."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.orders.models import Order, OrderStatus
from apps.shipping.dispatch import order_ready_for_shipment


@pytest.fixture
def status(db):
    return OrderStatus.objects.create(name="Нове", sort_order=0)


@pytest.mark.django_db
def test_order_ready_for_shipment_cod(status):
    order = Order.objects.create(
        status=status,
        first_name="A",
        last_name="B",
        email="a@b.c",
        phone="+380501234567",
        delivery_type=Order.DELIVERY_NP,
        payment_method=Order.PAYMENT_CASH_ON_DELIVERY,
        total=Decimal("100"),
    )
    assert order_ready_for_shipment(order) is True


@pytest.mark.django_db
def test_order_ready_for_shipment_unpaid_card(status):
    order = Order.objects.create(
        status=status,
        first_name="A",
        last_name="B",
        email="a@b.c",
        phone="+380501234567",
        delivery_type=Order.DELIVERY_NP,
        payment_method=Order.PAYMENT_CARD,
        is_paid=False,
        total=Decimal("100"),
    )
    assert order_ready_for_shipment(order) is False


@pytest.mark.django_db
@patch("apps.shipping.tasks.create_ttn_for_order.delay")
def test_dispatch_np_cod(mock_delay, status):
    from apps.shipping.dispatch import dispatch_shipment_for_order

    order = Order.objects.create(
        status=status,
        first_name="A",
        last_name="B",
        email="a@b.c",
        phone="+380501234567",
        delivery_type=Order.DELIVERY_NP,
        payment_method=Order.PAYMENT_CASH_ON_DELIVERY,
        total=Decimal("100"),
    )
    dispatch_shipment_for_order(order.pk)
    mock_delay.assert_called_once_with(order.pk)
