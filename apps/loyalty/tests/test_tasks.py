"""Tests for loyalty tasks: accrue coins, birthday coupons, expiration."""

import pytest
from decimal import Decimal


@pytest.fixture
def customer(db):
    from apps.customers.models import Customer
    return Customer.objects.create_user(
        email="loyal@svitpc.ua",
        password="pass",
        first_name="Тест",
        birth_date=None,
    )


@pytest.mark.django_db
def test_accrue_order_bonuses(customer):
    from apps.orders.models import Order, OrderStatus
    from apps.loyalty.tasks import accrue_order_bonuses

    status = OrderStatus.objects.create(name="Доставлено", is_completed=True)
    order = Order.objects.create(
        customer=customer,
        first_name="Тест", last_name="Юзер",
        phone="+380", email="loyal@svitpc.ua",
        total=Decimal("1000.00"),
        status=status,
    )
    accrue_order_bonuses(order.pk)
    customer.refresh_from_db()
    assert customer.bonus_balance == Decimal("1")


@pytest.mark.django_db
def test_accrue_no_customer_order(db):
    """accrue should silently pass if order has no customer."""
    from apps.orders.models import Order, OrderStatus
    from apps.loyalty.tasks import accrue_order_bonuses

    status = OrderStatus.objects.create(name="Доставлено", is_completed=True)
    order = Order.objects.create(
        customer=None,
        first_name="Анон", last_name="Юзер",
        phone="+380", email="anon@example.com",
        total=Decimal("500.00"),
        status=status,
    )
    accrue_order_bonuses(order.pk)  # should not raise


@pytest.mark.django_db
def test_birthday_greetings_creates_coupon(db, settings):
    from datetime import date

    from apps.customers.models import Customer
    from apps.loyalty.tasks import send_birthday_greetings
    from apps.loyalty.models import Coupon

    settings.EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
    settings.SMS_API_KEY = ""

    today = date.today()
    cust = Customer.objects.create_user(
        email="bday@svitpc.ua",
        password="pass",
        birth_date=today,
        is_active=True,
    )

    send_birthday_greetings()
    coupon = Coupon.objects.filter(code__startswith="BDAY-").first()
    assert coupon is not None
    assert coupon.discount_value == 10
    assert coupon.customer_id == cust.pk
    cust.refresh_from_db()
    assert cust.bonus_balance == Decimal("0")


@pytest.mark.django_db
def test_birthday_greetings_idempotent(db, settings):
    from datetime import date
    from unittest.mock import patch

    from apps.customers.models import Customer
    from apps.loyalty.tasks import send_birthday_greetings

    settings.EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
    settings.SMS_API_KEY = ""

    today = date.today()
    Customer.objects.create_user(
        email="bday2@svitpc.ua",
        password="pass",
        birth_date=today,
        is_active=True,
    )

    with patch("apps.notifications.service.send_notification"):
        send_birthday_greetings()
        send_birthday_greetings()

    from apps.loyalty.models import BonusTransaction

    assert (
        BonusTransaction.objects.filter(
            transaction_type=BonusTransaction.TYPE_BIRTHDAY,
            customer__email="bday2@svitpc.ua",
        ).count()
        == 1
    )
