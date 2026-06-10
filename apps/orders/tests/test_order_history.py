"""Tests for automatic OrderHistory rows."""

from decimal import Decimal

import pytest

from apps.orders.models import Order, OrderHistory, OrderStatus


@pytest.fixture
def order_statuses(db):
    new = OrderStatus.objects.create(name="Нове", sort_order=1)
    shipped = OrderStatus.objects.create(name="Відправлено", sort_order=2)
    return new, shipped


@pytest.fixture
def order(order_statuses):
    new, _ = order_statuses
    return Order.objects.create(
        first_name="Іван",
        last_name="Петренко",
        email="ivan@example.com",
        phone="+380501112233",
        total=Decimal("100.00"),
        status=new,
    )


@pytest.mark.django_db
def test_new_order_creates_initial_history(order):
    assert OrderHistory.objects.filter(order=order).count() == 1
    entry = OrderHistory.objects.get(order=order)
    assert entry.status_id == order.status_id


@pytest.mark.django_db
def test_status_change_appends_history(order, order_statuses):
    _, shipped = order_statuses
    order.status = shipped
    order.save(update_fields=["status"])

    statuses = list(order.history.order_by("created_at").values_list("status_id", flat=True))
    assert statuses == [order_statuses[0].pk, shipped.pk]


@pytest.mark.django_db
def test_unchanged_status_does_not_duplicate_history(order):
    order.comment = "updated"
    order.save(update_fields=["comment"])
    assert OrderHistory.objects.filter(order=order).count() == 1
