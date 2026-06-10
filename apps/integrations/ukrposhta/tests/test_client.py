"""Ukrposhta client tests."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.django_db
def test_calc_delivery_price(settings):
    settings.UKRPOSHTA_BEARER = "bearer"
    settings.UKRPOSHTA_TOKEN = "token"
    settings.UP_SENDER_POSTCODE = "49000"

    from apps.integrations.ukrposhta.client import UkrPoshtaClient

    client = UkrPoshtaClient()
    with patch.object(client, "_request", return_value={"deliveryPrice": 88.0}):
        price = client.calc_delivery_price("01001", weight_kg=2.0, declared_value=500)
    assert price == Decimal("88.0")


@pytest.mark.django_db
def test_create_shipment_requires_sender_uuid(settings):
    settings.UKRPOSHTA_BEARER = "bearer"
    settings.UKRPOSHTA_TOKEN = "token"
    settings.UP_SENDER_CLIENT_UUID = ""

    from apps.integrations.ukrposhta.client import UkrPoshtaClient

    client = UkrPoshtaClient()
    order = MagicMock()
    order.pk = 1
    assert client.create_shipment(order) is None
