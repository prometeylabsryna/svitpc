"""Nova Poshta city search tests."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from apps.shipping.models import NovaPoshtaCity, NovaPoshtaWarehouse
from apps.shipping.services import search_np_cities, search_np_warehouses


@pytest.mark.django_db
def test_search_kyiv_prefers_city_over_oblast_villages():
    NovaPoshtaCity.objects.create(name="Київ", ref="kyiv-ref", area="Київська")
    NovaPoshtaCity.objects.create(
        name="Андріївка (Київська обл.)",
        ref="and-ref",
        area="Київська",
    )

    results = list(search_np_cities("Київ"))

    assert results
    assert results[0].name == "Київ"


@pytest.mark.django_db
def test_search_kyiv_english_alias():
    NovaPoshtaCity.objects.create(name="Київ", ref="kyiv-ref", area="Київська", name_en="Киев")
    NovaPoshtaCity.objects.create(
        name="Андріївка (Київська обл.)",
        ref="and-ref",
        area="Київська",
    )

    results = list(search_np_cities("Kyiv"))

    assert results
    assert results[0].name == "Київ"


@pytest.mark.django_db
def test_search_np_cities_uses_api_when_db_empty(settings):
    settings.NOVA_POSHTA_API_KEY = "test_key"
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "success": True,
        "data": [
            {
                "Addresses": [
                    {
                        "Present": "м. Київ, Київська обл.",
                        "DeliveryCityRef": "kyiv-ref",
                        "AreaDescription": "Київська",
                    }
                ]
            }
        ],
    }
    mock_resp.raise_for_status = lambda: None

    with patch.object(httpx, "post", return_value=mock_resp):
        results = list(search_np_cities("Київ"))

    assert len(results) == 1
    assert results[0].name == "м. Київ, Київська обл."
    assert results[0].ref == "kyiv-ref"
    assert results[0].area == "Київська"


@pytest.mark.django_db
def test_search_np_warehouses_uses_api(settings):
    settings.NOVA_POSHTA_API_KEY = "test_key"
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "success": True,
        "data": [{"Description": "Відділення №1", "Ref": "wh-ref-1"}],
    }
    mock_resp.raise_for_status = lambda: None

    with patch.object(httpx, "post", return_value=mock_resp):
        results = search_np_warehouses("city-ref", "1")

    assert results == [{"name": "Відділення №1", "ref": "wh-ref-1"}]


@pytest.mark.django_db
def test_search_np_warehouses_db_fallback(settings):
    settings.NOVA_POSHTA_API_KEY = ""
    city = NovaPoshtaCity.objects.create(name="Дніпро", ref="dnipro-ref", area="Дніпровська")
    NovaPoshtaWarehouse.objects.create(city=city, name="Відділення №44", ref="wh-44", number="44")

    results = search_np_warehouses("dnipro-ref", "44")

    assert results == [{"name": "Відділення №44", "ref": "wh-44"}]
