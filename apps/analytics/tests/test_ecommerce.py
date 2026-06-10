"""Tests for analytics ecommerce payload helpers."""

import json
from decimal import Decimal

import pytest

from apps.analytics.ecommerce import (
    cart_action_payload,
    ecommerce_json,
    order_purchase_payload,
    product_list_payload,
    product_view_payload,
)


@pytest.mark.django_db
def test_product_view_payload(product_factory):
    product = product_factory(name="GPU &#039;RTX&#039;", price=Decimal("10000.50"))
    payload = product_view_payload(product)
    assert payload["id"] == product.pk
    assert payload["name"] == "GPU 'RTX'"
    assert payload["price"] == "10000.50"


@pytest.mark.django_db
def test_order_purchase_payload(product_factory):
    from apps.orders.models import Order, OrderItem, OrderStatus

    status = OrderStatus.objects.create(name="New", sort_order=0)
    product = product_factory(name="Mouse", price=Decimal("500.00"))
    order = Order.objects.create(
        status=status,
        first_name="Ivan",
        last_name="Test",
        email="a@b.c",
        phone="+380",
        total=Decimal("1000.00"),
    )
    OrderItem.objects.create(order=order, product=product, name=product.name, price=product.price, qty=2)

    payload = order_purchase_payload(order)
    assert payload["order_id"] == str(order.pk)
    assert payload["total"] == "1000.00"
    assert len(payload["items"]) == 1
    assert payload["items"][0]["item_id"] == str(product.pk)
    assert payload["items"][0]["quantity"] == 2


def test_cart_action_payload():
    payload = cart_action_payload(product_id=7, name="Keyboard", price="1200", qty=1)
    assert payload == {"id": 7, "name": "Keyboard", "price": "1200.00", "qty": 1}


@pytest.mark.django_db
def test_product_list_payload(product_factory):
    products = [product_factory(name=f"P{i}", price=Decimal("100")) for i in range(2)]
    payload = product_list_payload(list_id="cat-1", list_name="Cat", products=products)
    assert payload["list_id"] == "cat-1"
    assert len(payload["items"]) == 2
    assert payload["items"][0]["item_id"] == str(products[0].pk)


def test_ecommerce_json_valid_json():
    raw = ecommerce_json({"name": '15" monitor', "id": 1})
    parsed = json.loads(raw)
    assert parsed["name"] == '15" monitor'
