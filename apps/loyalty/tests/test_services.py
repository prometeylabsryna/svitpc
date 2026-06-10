"""Tests for loyalty services."""

from decimal import Decimal

import pytest

from apps.loyalty.models import Coupon
from apps.loyalty.services import (
    LoyaltyError,
    apply_loyalty_to_order,
    calculate_coupon_discount,
    resolve_checkout_loyalty,
    validate_coupon,
)


@pytest.mark.django_db
def test_validate_coupon_percent(customer_factory):
    customer = customer_factory()
    coupon = Coupon.objects.create(
        code="SAVE10",
        discount_type="percent",
        discount_value=10,
        is_active=True,
    )
    result = validate_coupon("save10", customer=customer, subtotal=Decimal("1000"))
    assert result.pk == coupon.pk
    assert calculate_coupon_discount(coupon, Decimal("1000")) == Decimal("100.00")


@pytest.mark.django_db
def test_validate_coupon_personal_only(customer_factory):
    customer = customer_factory()
    other = customer_factory(email="other@svitpc.ua")
    Coupon.objects.create(
        code="PERSONAL",
        customer=customer,
        discount_type="fixed",
        discount_value=50,
        is_active=True,
    )
    with pytest.raises(LoyaltyError):
        validate_coupon("PERSONAL", customer=other, subtotal=Decimal("500"))


@pytest.mark.django_db
def test_coin_reward_coupon_capped_at_20_percent(customer_factory):
    customer = customer_factory()
    coupon = Coupon.objects.create(
        code="COIN-TEST",
        customer=customer,
        discount_type="fixed",
        discount_value=700,
        source=Coupon.SOURCE_COIN_REWARD,
        is_active=True,
    )
    discount = calculate_coupon_discount(coupon, Decimal("1000"))
    assert discount == Decimal("200.00")


@pytest.mark.django_db
def test_resolve_checkout_with_coupon(customer_factory):
    customer = customer_factory()
    Coupon.objects.create(
        code="OFF100",
        discount_type="fixed",
        discount_value=100,
        is_active=True,
    )
    totals = resolve_checkout_loyalty(
        subtotal=Decimal("1000"),
        customer=customer,
        coupon_code="OFF100",
    )
    assert totals.discount == Decimal("100")
    assert totals.total == Decimal("900")


@pytest.mark.django_db
def test_apply_loyalty_deactivates_exhausted_coupon(customer_factory):
    from apps.orders.models import Order, OrderStatus

    customer = customer_factory()
    status = OrderStatus.objects.create(name="Нове", is_completed=False)
    coupon = Coupon.objects.create(
        code="COIN-ONCE",
        customer=customer,
        discount_type="fixed",
        discount_value=100,
        max_uses=1,
        source=Coupon.SOURCE_COIN_REWARD,
        is_active=True,
    )
    order = Order.objects.create(
        customer=customer,
        first_name="Тест",
        last_name="Юзер",
        phone="+380",
        email=customer.email,
        total=Decimal("900.00"),
        discount=Decimal("100.00"),
        status=status,
        coupon=coupon,
    )

    apply_loyalty_to_order(order, customer=customer, coupon=coupon)

    coupon.refresh_from_db()
    assert coupon.used_count == 1
    assert coupon.is_active is False
