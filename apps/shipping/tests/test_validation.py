"""Shipping validation tests."""

import pytest

from apps.orders.models import Order
from apps.shipping.validation import validate_checkout_step1


@pytest.mark.parametrize(
    "data,expected_fragment",
    [
        ({"delivery_type": Order.DELIVERY_NP}, "місто"),
        ({"delivery_type": "unknown"}, "спосіб доставки"),
    ],
)
def test_validate_checkout_step1_errors(data, expected_fragment):
    errors = validate_checkout_step1(
        {
            "first_name": "Тест",
            "last_name": "Клієнт",
            "phone": "+380501234567",
            **data,
        }
    )
    assert any(expected_fragment in err.lower() for err in errors)


def test_validate_checkout_step1_pickup_ok():
    data = {
        "first_name": "Тест",
        "last_name": "Клієнт",
        "phone": "0501234567",
        "delivery_type": Order.DELIVERY_PICKUP,
    }
    errors = validate_checkout_step1(data)
    assert errors == []
    assert data["phone"] == "+380501234567"


def test_validate_checkout_step1_rejects_invalid_phone():
    data = {
        "first_name": "Тест",
        "last_name": "Клієнт",
        "phone": "12345",
        "delivery_type": Order.DELIVERY_PICKUP,
    }
    errors = validate_checkout_step1(data)
    assert any("телефон" in err.lower() for err in errors)
