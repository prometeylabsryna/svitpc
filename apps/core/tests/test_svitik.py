"""Tests for Pan Svitik hint helpers."""

from decimal import Decimal

import pytest

from apps.core.svitik import (
    cart_coin_hint,
    cart_coin_hint_message,
    cart_coin_hint_parts,
    cart_coin_hint_payload,
    min_order_coin_gap,
    product_purchase_tip,
    svitik_mascot_file,
)


@pytest.mark.parametrize(
    "total,current,next_coins,remaining",
    [
        (Decimal("250"), 0, 1, Decimal("50")),
        (Decimal("2600"), 1, 10, Decimal("400")),
        (Decimal("4800"), 10, 15, Decimal("200")),
        (Decimal("20000"), 50, None, None),
    ],
)
def test_cart_coin_hint(total, current, next_coins, remaining):
    hint = cart_coin_hint(total)
    assert hint.current_coins == current
    assert hint.next_coins == next_coins
    assert hint.remaining_uah == remaining


def test_cart_coin_hint_message_below_minimum():
    hint = cart_coin_hint(Decimal("100"))
    msg = cart_coin_hint_message(hint)
    assert msg is not None
    assert hint.remaining_uah is not None
    assert str(int(hint.remaining_uah)) in msg.replace("\u00a0", " ")
    assert "монет" in msg


def test_cart_coin_hint_message_next_tier():
    hint = cart_coin_hint(Decimal("2600"))
    msg = cart_coin_hint_message(hint)
    assert msg is not None
    assert "2" in msg.replace("\u00a0", " ")
    assert "400" in msg
    assert "1" in msg
    assert "10" in msg


def test_cart_coin_hint_parts_next_tier():
    hint = cart_coin_hint(Decimal("3168"))
    parts = cart_coin_hint_parts(hint)
    assert parts is not None
    assert parts.kind == "next_tier"
    assert parts.total == "3\u00a0168 ₴"
    assert parts.remaining == "1\u00a0832 ₴"
    assert parts.coins == 10
    assert parts.next_coins == 15


def test_cart_coin_hint_parts_next_tier_first_band():
    hint = cart_coin_hint(Decimal("1778"))
    parts = cart_coin_hint_parts(hint)
    assert parts is not None
    assert parts.kind == "next_tier"
    assert parts.coins == 1
    assert parts.next_coins == 10


def test_cart_coin_hint_parts_earned():
    hint = cart_coin_hint(Decimal("25000"))
    parts = cart_coin_hint_parts(hint)
    assert parts is not None
    assert parts.kind == "earned"
    assert parts.coins == 50


def test_cart_coin_hint_message_max_tier():
    hint = cart_coin_hint(Decimal("25000"))
    msg = cart_coin_hint_message(hint)
    assert msg is not None
    assert "50" in msg


def test_cart_coin_hint_payload_includes_coins():
    hint = cart_coin_hint(Decimal("2600"))
    payload = cart_coin_hint_payload(hint)
    assert payload is not None
    assert payload["variant"] == "cart"
    assert payload["coins"] == 1
    assert payload["mascot"] == "pan-svitik-coins.png"


def test_svitik_mascot_file_maps_variants():
    assert svitik_mascot_file(variant="welcome") == "pan-svitik-choice.png"
    assert svitik_mascot_file(variant="choice") == "pan-svitik-choice.png"
    assert svitik_mascot_file(variant="cart") == "pan-svitik-coins.png"
    assert svitik_mascot_file(variant="checkout", mascot="coins") == "pan-svitik-coins.png"
    assert svitik_mascot_file(variant="success") == "pan-svitik-celebrate.png"
    assert svitik_mascot_file(variant="guide") == "pan-svitik-tech.png"


def test_min_order_coin_gap():
    assert min_order_coin_gap(Decimal("100")) == Decimal("200")
    assert min_order_coin_gap(Decimal("500")) is None


@pytest.mark.django_db
def test_product_purchase_tip_laptop(category_factory, product_factory):
    cat = category_factory(name="Ноутбуки", slug="noutbuky")
    product = product_factory()
    product.categories.add(cat)
    tip = product_purchase_tip(product)
    assert tip is not None
    assert "ноутбук" in tip.lower()


@pytest.mark.django_db
def test_product_purchase_tip_unknown(product_factory):
    product = product_factory()
    assert product_purchase_tip(product) is None
