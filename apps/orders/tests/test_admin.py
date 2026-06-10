"""Tests for order admin status field."""

from decimal import Decimal

import pytest

from apps.orders.admin import OrderAdminForm
from apps.orders.models import Order, OrderStatus
from apps.orders.statuses import ORDER_STATUS_NAMES


@pytest.fixture
def order_statuses(db):
    statuses = []
    for index, name in enumerate(ORDER_STATUS_NAMES, start=1):
        statuses.append(
            OrderStatus.objects.create(
                name=name,
                sort_order=index,
                is_completed=name == "Виконано",
            )
        )
    return statuses


@pytest.fixture
def order(order_statuses):
    return Order.objects.create(
        first_name="Іван",
        last_name="Петренко",
        email="ivan@example.com",
        phone="+380501112233",
        total=Decimal("100.00"),
        status=order_statuses[0],
    )


@pytest.mark.django_db
def test_admin_form_limits_status_choices(order_statuses, order):
    OrderStatus.objects.create(name="Доставлено", sort_order=99, is_completed=True)

    form = OrderAdminForm(instance=order)
    names = set(form.fields["status"].queryset.values_list("name", flat=True))

    assert names == set(ORDER_STATUS_NAMES)


@pytest.mark.django_db
def test_changing_status_to_completed(order_statuses, order):
    done = order_statuses[2]
    order.status = done
    order.save(update_fields=["status"])

    order.refresh_from_db()
    assert order.status_id == done.pk
    assert done.is_completed is True
