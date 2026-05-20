"""Nova Poshta client unit tests (mocked httpx)."""

import pytest
import responses as resp_lib


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
    result = client.create_ttn(fake_order)
    assert result is None


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
