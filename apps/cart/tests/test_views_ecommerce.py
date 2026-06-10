"""Tests for cart view HX-Trigger ecommerce payloads."""

import json
from decimal import Decimal

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_cart_add_hx_trigger_svitik(client, product_factory):
    product = product_factory(name="Coin hint", slug="coin-hint", price=Decimal("2600.00"))
    url = reverse("cart:add", kwargs={"product_id": product.pk})
    response = client.post(url)
    trigger = json.loads(response["HX-Trigger"])
    assert "svitik" in trigger
    assert trigger["svitik"]["variant"] == "choice"
    assert trigger["svitik"]["coins"] == 1
    assert "400" in trigger["svitik"]["message"]


@pytest.mark.django_db
def test_cart_add_hx_trigger(client, product_factory):
    product = product_factory(name="Add me", slug="add-me", price=Decimal("250.00"))
    url = reverse("cart:add", kwargs={"product_id": product.pk})
    response = client.post(url)
    assert response.status_code == 204
    trigger = json.loads(response["HX-Trigger"])
    assert trigger["cartUpdated"] == 1
    assert trigger["cart:add"]["id"] == product.pk
    assert trigger["cart:add"]["name"] == "Add me"
    assert trigger["cart:add"]["price"] == "250.00"
    assert trigger["cart:add"]["qty"] == 1
    assert trigger["toast"]["type"] == "success"
    assert "кошика" in trigger["toast"]["message"]


@pytest.mark.django_db
def test_cart_add_hx_trigger_ascii_json_with_cyrillic_product_name(client, product_factory):
    product = product_factory(name="Ноутбук Lenovo", slug="lenovo", price=Decimal("1000.00"))
    url = reverse("cart:add", kwargs={"product_id": product.pk})
    response = client.post(url, HTTP_HX_REQUEST="true")
    raw = response["HX-Trigger"]
    assert raw.isascii()
    trigger = json.loads(raw)
    assert trigger["cartUpdated"] == 1
    assert trigger["cart:add"]["name"] == "Ноутбук Lenovo"


@pytest.mark.django_db
def test_cart_remove_hx_trigger(client, product_factory):
    product = product_factory(name="Remove me", slug="remove-me", price=Decimal("99.00"))
    add_url = reverse("cart:add", kwargs={"product_id": product.pk})
    client.post(add_url)
    remove_url = reverse("cart:remove", kwargs={"product_id": product.pk})
    response = client.post(remove_url)
    assert response.status_code == 200
    trigger = json.loads(response["HX-Trigger"])
    assert trigger["cartUpdated"] == 0
    assert trigger["cart:remove"]["id"] == product.pk
    assert trigger["cart:remove"]["qty"] == 1


@pytest.mark.django_db
def test_cart_remove_updates_total_in_html(client, product_factory):
    cheap = product_factory(name="Cheap", slug="cheap", price=Decimal("100.00"))
    pricey = product_factory(name="Pricey", slug="pricey", price=Decimal("3456.00"))
    client.post(reverse("cart:add", kwargs={"product_id": cheap.pk}))
    client.post(reverse("cart:add", kwargs={"product_id": pricey.pk}))

    response = client.post(reverse("cart:remove", kwargs={"product_id": pricey.pk}))
    html = response.content.decode().replace("\xa0", " ")

    assert "3 556" not in html
    assert 'id="cart-total">100' in html


@pytest.mark.django_db
def test_cart_remove_last_item_shows_empty_state(client, product_factory):
    product = product_factory(name="Only one", slug="only-one", price=Decimal("50.00"))
    client.post(reverse("cart:add", kwargs={"product_id": product.pk}))

    response = client.post(reverse("cart:remove", kwargs={"product_id": product.pk}))
    html = response.content.decode()

    assert "cart-empty" in html
    assert 'id="cart-total"' not in html
