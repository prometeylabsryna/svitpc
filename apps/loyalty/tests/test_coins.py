"""Tests for SvitPC coin loyalty logic."""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.loyalty.coins import (
    accrue_coins_for_order,
    coins_for_order,
    coins_for_order_total,
    expire_customer_coins,
    next_milestone_progress,
    pending_coin_orders_for_customer,
    process_milestone_rewards,
    total_pending_coins,
)
from apps.loyalty.models import BonusTransaction, Coupon


@pytest.mark.parametrize(
    "total,expected",
    [
        (Decimal("299"), 0),
        (Decimal("300"), 1),
        (Decimal("2999"), 1),
        (Decimal("3000"), 10),
        (Decimal("4999"), 10),
        (Decimal("5000"), 15),
        (Decimal("9999"), 15),
        (Decimal("10000"), 25),
        (Decimal("19999"), 25),
        (Decimal("20000"), 50),
        (Decimal("21999"), 50),
    ],
)
def test_coins_for_order_total(total, expected):
    assert coins_for_order_total(total) == expected


def test_next_milestone_progress():
    progress = next_milestone_progress(30)
    assert progress is not None
    assert progress.current == 30
    assert progress.target == 50
    assert progress.remaining == 20
    assert progress.reward_uah == Decimal("700")


@pytest.mark.django_db
def test_accrue_coins_idempotent_per_order(customer_factory):
    """Повторний виклик accrue для того ж замовлення не подвоює монети."""
    from apps.orders.models import Order, OrderStatus

    customer = customer_factory()
    status = OrderStatus.objects.create(name="Доставлено", is_completed=True)
    order = Order.objects.create(
        customer=customer,
        first_name="Тест",
        last_name="Юзер",
        phone="+380",
        email=customer.email,
        total=Decimal("2999.00"),  # 1 монета — нижче першого milestone (10)
        status=status,
    )
    first = accrue_coins_for_order(order)
    second = accrue_coins_for_order(order)

    assert first is not None
    assert second is None
    customer.refresh_from_db()
    assert customer.bonus_balance == Decimal("1")
    assert BonusTransaction.objects.filter(
        order=order, transaction_type=BonusTransaction.TYPE_EARN
    ).count() == 1


@pytest.mark.django_db
def test_accrue_coins_example_order(customer_factory):
    from apps.orders.models import Order, OrderStatus

    customer = customer_factory()
    status = OrderStatus.objects.create(name="Доставлено", is_completed=True)
    order = Order.objects.create(
        customer=customer,
        first_name="Тест",
        last_name="Юзер",
        phone="+380",
        email=customer.email,
        total=Decimal("21999.00"),
        status=status,
    )
    accrue_coins_for_order(order)
    customer.refresh_from_db()
    assert customer.bonus_balance == Decimal("0")
    coupon = Coupon.objects.filter(customer=customer, source=Coupon.SOURCE_COIN_REWARD).first()
    assert coupon is not None
    assert coupon.discount_value == Decimal("700")


@pytest.mark.django_db
def test_accrue_coins_partial_balance(customer_factory):
    from apps.orders.models import Order, OrderStatus

    customer = customer_factory(bonus_balance=Decimal("5"))
    status = OrderStatus.objects.create(name="Доставлено", is_completed=True)
    order = Order.objects.create(
        customer=customer,
        first_name="Тест",
        last_name="Юзер",
        phone="+380",
        email=customer.email,
        total=Decimal("3500.00"),
        status=status,
    )
    accrue_coins_for_order(order)
    customer.refresh_from_db()
    assert customer.bonus_balance == Decimal("5")


@pytest.mark.django_db
def test_milestone_rewards_multiple(customer_factory):
    customer = customer_factory(bonus_balance=Decimal("35"))
    issued = process_milestone_rewards(customer)
    customer.refresh_from_db()
    assert len(issued) == 2
    assert customer.bonus_balance == Decimal("0")
    values = sorted(c.discount_value for c in issued)
    assert values == [Decimal("100"), Decimal("300")]


@pytest.mark.django_db
def test_expire_customer_coins(customer_factory):
    customer = customer_factory(bonus_balance=Decimal("10"))
    BonusTransaction.objects.create(
        customer=customer,
        transaction_type=BonusTransaction.TYPE_EARN,
        amount=Decimal("10"),
        balance_after=Decimal("10"),
        expires_at=timezone.now() - timezone.timedelta(days=1),
        description="test",
    )
    expired = expire_customer_coins(customer)
    customer.refresh_from_db()
    assert expired == 10
    assert customer.bonus_balance == Decimal("0")
    assert BonusTransaction.objects.filter(
        customer=customer,
        transaction_type=BonusTransaction.TYPE_EXPIRE,
    ).exists()


@pytest.mark.django_db
def test_pending_coin_orders_for_customer(customer_factory):
    from apps.orders.models import Order, OrderStatus

    customer = customer_factory()
    pending_status = OrderStatus.objects.create(name="Нове", is_completed=False)
    completed_status = OrderStatus.objects.create(name="Доставлено", is_completed=True)

    open_order = Order.objects.create(
        customer=customer,
        first_name="Тест",
        last_name="Юзер",
        phone="+380",
        email=customer.email,
        total=Decimal("21999.00"),
        status=pending_status,
    )
    Order.objects.create(
        customer=customer,
        first_name="Тест",
        last_name="Юзер",
        phone="+380",
        email=customer.email,
        total=Decimal("3500.00"),
        status=completed_status,
    )

    pending = pending_coin_orders_for_customer(customer)
    assert len(pending) == 1
    assert pending[0].order_id == open_order.pk
    assert pending[0].coins == 50
    assert total_pending_coins(customer) == 50
    assert coins_for_order(open_order) == 50
