"""Shipping validation tests."""

import pytest

from apps.orders.models import Order
from apps.shipping.validation import validate_checkout_step1


@pytest.mark.parametrize(
    "data,expected_fragment",
    [
        ({"delivery_type": Order.DELIVERY_NP}, "місто"),
        ({"delivery_type": Order.DELIVERY_UP, "city": "Київ"}, "індекс"),
        ({"delivery_type": Order.DELIVERY_UP, "city": "Київ", "postcode": "123"}, "5 цифр"),
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
    errors = validate_checkout_step1(
        {
            "first_name": "Тест",
            "last_name": "Клієнт",
            "phone": "+380501234567",
            "delivery_type": Order.DELIVERY_PICKUP,
        }
    )
    assert errors == []
