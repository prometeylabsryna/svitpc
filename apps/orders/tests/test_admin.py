"""Tests for order admin status field."""

from decimal import Decimal

import pytest

from apps.orders.forms import OrderAdminForm
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
def test_admin_form_requires_np_refs_for_manual_order(order_statuses):
    status = order_statuses[0]
    form = OrderAdminForm(
        data={
            "status": status.pk,
            "first_name": "Іван",
            "last_name": "Петренко",
            "email": "ivan@example.com",
            "phone": "+380501112233",
            "delivery_type": Order.DELIVERY_NP,
            "city": "Київ",
            "city_ref": "",
            "warehouse": "Відділення №1",
            "warehouse_ref": "",
            "payment_method": Order.PAYMENT_CASH_ON_DELIVERY,
            "is_paid": False,
            "total": "100.00",
            "delivery_cost": "0",
            "discount": "0",
            "bonus_used": "0",
            "ttn": "",
            "comment": "",
            "payment_id": "",
            "fiscal_check_url": "",
        }
    )

    assert not form.is_valid()
    assert "city" in form.errors or "warehouse" in form.errors


@pytest.mark.django_db
def test_admin_form_accepts_np_order_with_refs(order_statuses):
    status = order_statuses[0]
    form = OrderAdminForm(
        data={
            "status": status.pk,
            "first_name": "Іван",
            "last_name": "Петренко",
            "email": "ivan@example.com",
            "phone": "+380501112233",
            "delivery_type": Order.DELIVERY_NP,
            "city": "Київ",
            "city_ref": "city-ref-1",
            "warehouse": "Відділення №1",
            "warehouse_ref": "wh-ref-1",
            "payment_method": Order.PAYMENT_CASH_ON_DELIVERY,
            "is_paid": False,
            "total": "100.00",
            "delivery_cost": "0",
            "discount": "0",
            "bonus_used": "0",
            "ttn": "",
            "comment": "",
            "payment_id": "",
            "fiscal_check_url": "",
        }
    )

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_changing_status_to_completed(order_statuses, order):
    done = order_statuses[2]
    order.status = done
    order.save(update_fields=["status"])

    order.refresh_from_db()
    assert order.status_id == done.pk
    assert done.is_completed is True
