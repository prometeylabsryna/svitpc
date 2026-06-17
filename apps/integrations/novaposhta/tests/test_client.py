"""Nova Poshta client unit tests (mocked httpx)."""

import pytest


@pytest.mark.django_db
def test_search_cities_returns_list(settings):
    """search_cities should parse API response correctly."""
    settings.NOVA_POSHTA_API_KEY = "test_key"
    import httpx
    from unittest.mock import patch, MagicMock

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "success": True,
        "data": [{"Addresses": [{"Present": "Київ", "Ref": "abc123"}]}],
    }
    mock_resp.raise_for_status = lambda: None

    from apps.integrations.novaposhta.client import NovaPoshtaClient
    with patch.object(httpx, "post", return_value=mock_resp):
        client = NovaPoshtaClient()
        cities = client.search_cities("Київ")
    assert isinstance(cities, list)


@pytest.mark.django_db
def test_create_ttn_missing_sender_returns_none(settings):
    """create_ttn returns None when sender settings are missing."""
    settings.NOVA_POSHTA_API_KEY = "test_key"
    settings.NP_SENDER_REF = ""
    settings.NP_SENDER_CONTACT_REF = ""
    settings.NP_SENDER_PHONE = ""
    settings.NP_SENDER_CITY_REF = ""
    settings.NP_SENDER_WAREHOUSE_REF = ""

    from apps.integrations.novaposhta.client import NovaPoshtaClient
    from unittest.mock import MagicMock

    client = NovaPoshtaClient()
    fake_order = MagicMock()
    result, error = client.create_ttn(fake_order)
    assert result is None
    assert error


@pytest.mark.django_db
def test_create_ttn_success(settings):
    """create_ttn creates recipient counterparty then InternetDocument."""
    settings.NOVA_POSHTA_API_KEY = "test_key"
    settings.NP_SENDER_REF = "sender-ref"
    settings.NP_SENDER_CONTACT_REF = "contact-ref"
    settings.NP_SENDER_PHONE = "+380683135103"
    settings.NP_SENDER_CITY_REF = "city-sender"
    settings.NP_SENDER_WAREHOUSE_REF = "wh-sender"

    import httpx
    from unittest.mock import MagicMock, patch

    counterparty_resp = MagicMock()
    counterparty_resp.json.return_value = {
        "success": True,
        "data": [{
            "Ref": "recipient-ref",
            "ContactPerson": {"data": [{"Ref": "recipient-contact-ref"}]},
        }],
    }
    counterparty_resp.raise_for_status = lambda: None

    ttn_resp = MagicMock()
    ttn_resp.json.return_value = {
        "success": True,
        "data": [{"IntDocNumber": "20450000000001"}],
    }
    ttn_resp.raise_for_status = lambda: None

    from apps.integrations.novaposhta.client import NovaPoshtaClient
    from unittest.mock import MagicMock

    fake_order = MagicMock()
    fake_order.pk = 42
    fake_order.payment_method = "card"
    fake_order.city_ref = "city-recipient"
    fake_order.warehouse_ref = "wh-recipient"
    fake_order.phone = "+380 (50) 123-45-67"
    fake_order.first_name = "Іван"
    fake_order.last_name = "Петренко"
    fake_order.email = "ivan@test.ua"
    fake_order.total = 500
    fake_order.items.select_related.return_value.all.return_value = []

    with patch.object(httpx, "post", side_effect=[counterparty_resp, ttn_resp]) as mock_post:
        client = NovaPoshtaClient()
        result, error = client.create_ttn(fake_order)

    assert result == "20450000000001"
    assert error == ""
    assert mock_post.call_count == 2
    doc_payload = mock_post.call_args_list[1].kwargs["json"]["methodProperties"]
    assert doc_payload["Recipient"] == "recipient-ref"
    assert doc_payload["ContactRecipient"] == "recipient-contact-ref"
    assert doc_payload["PayerType"] == "Sender"
    assert doc_payload["PaymentMethod"] == "Cash"
    assert doc_payload["RecipientsPhone"] == "380501234567"


@pytest.mark.django_db
def test_normalize_np_phone():
    from apps.integrations.novaposhta.client import _latin_to_ukrainian, _normalize_np_phone, _np_name_part

    assert _normalize_np_phone("+380501234567") == "380501234567"
    assert _normalize_np_phone("0501234567") == "380501234567"
    assert _latin_to_ukrainian("test") == "тест"
    assert _np_name_part("test", fallback="Клієнт") == "тест"
    assert _np_name_part("Іван", fallback="Клієнт") == "Іван"


@pytest.mark.django_db
def test_track_ttn_empty_returns_none(settings):
    """track_ttn returns None when API returns empty data."""
    settings.NOVA_POSHTA_API_KEY = "test_key"
    import httpx
    from unittest.mock import patch, MagicMock

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"success": True, "data": []}
    mock_resp.raise_for_status = lambda: None

    from apps.integrations.novaposhta.client import NovaPoshtaClient
    with patch.object(httpx, "post", return_value=mock_resp):
        client = NovaPoshtaClient()
        result = client.track_ttn("59000000000000")
    assert result is None
