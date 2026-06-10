"""Checkout loyalty integration tests."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.customers.models import Customer
from apps.loyalty.models import Coupon
from apps.orders.models import Order


@pytest.fixture
def customer(db):
    return Customer.objects.create_user(
        email="checkout@svitpc.ua",
        password="pass",
        phone="+380501234567",
        birth_date="1990-01-15",
        bonus_balance=Decimal("10"),
    )


@pytest.fixture
def product(db, product_factory):
    return product_factory(slug="loyalty-product", price=Decimal("1000.00"))


@pytest.mark.django_db
def test_checkout_applies_coupon(client, customer, product):
    client.force_login(customer)
    session = client.session
    session["svitpc_cart"] = {
        str(product.pk): {
            "qty": 1,
            "price": str(product.price),
            "name": product.name,
            "slug": product.slug,
            "image_url": "",
        }
    }
    session.save()

    coupon = Coupon.objects.create(
        code="TEST10",
        discount_type="percent",
        discount_value=10,
        is_active=True,
    )

    client.post(
        reverse("checkout:step1"),
        {
            "first_name": "Тест",
            "last_name": "Клієнт",
            "phone": "+380501234567",
            "email": customer.email,
            "delivery_type": "pickup",
        },
    )
    client.post(
        reverse("checkout:step2"),
        {
            "payment_method": "cod",
            "coupon_code": coupon.code,
        },
    )
    response = client.post(reverse("checkout:confirm"))
    assert response.status_code == 302

    order = Order.objects.latest("pk")
    assert order.discount == Decimal("100.00")
    assert order.total == Decimal("900.00")
    assert order.coupon_id == coupon.pk

    customer.refresh_from_db()
    assert customer.bonus_balance == Decimal("10")
    coupon.refresh_from_db()
    assert coupon.used_count == 1


@pytest.mark.django_db
def test_used_coin_coupon_disappears_from_bonus_cabinet(client, customer, product):
    client.force_login(customer)
    session = client.session
    session["svitpc_cart"] = {
        str(product.pk): {
            "qty": 1,
            "price": str(product.price),
            "name": product.name,
            "slug": product.slug,
            "image_url": "",
        }
    }
    session.save()

    coupon = Coupon.objects.create(
        code="COIN-HFM34ZAA",
        customer=customer,
        discount_type="fixed",
        discount_value=100,
        max_uses=1,
        source=Coupon.SOURCE_COIN_REWARD,
        is_active=True,
    )

    bonus_url = reverse("loyalty:bonus")
    response = client.get(bonus_url)
    assert response.status_code == 200
    assert coupon.code in response.content.decode()

    client.post(
        reverse("checkout:step1"),
        {
            "first_name": "Тест",
            "last_name": "Клієнт",
            "phone": "+380501234567",
            "email": customer.email,
            "delivery_type": "pickup",
        },
    )
    client.post(
        reverse("checkout:step2"),
        {
            "payment_method": "cod",
            "coupon_code": coupon.code,
        },
    )
    response = client.post(reverse("checkout:confirm"))
    assert response.status_code == 302

    coupon.refresh_from_db()
    assert coupon.used_count == 1
    assert coupon.is_active is False

    response = client.get(bonus_url)
    assert response.status_code == 200
    assert coupon.code not in response.content.decode()
