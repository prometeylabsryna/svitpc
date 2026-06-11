"""Nova Poshta Celery task tests."""

from unittest.mock import MagicMock, patch

import pytest

from apps.integrations.novaposhta.tasks import (
    NP_WAREHOUSE_SYNC_CHUNK_SIZE,
    _sync_warehouses_for_cities,
    enqueue_np_warehouse_sync,
)
from apps.shipping.models import NovaPoshtaCity, NovaPoshtaWarehouse


@pytest.mark.django_db
def test_sync_warehouses_for_cities(settings):
    settings.NOVA_POSHTA_API_KEY = "test_key"
    city = NovaPoshtaCity.objects.create(name="Київ", ref="kyiv-ref", area="Київська")

    with patch("apps.integrations.novaposhta.tasks.NovaPoshtaClient") as client_cls:
        client_cls.return_value.get_warehouses.return_value = [
            {"Description": "Відділення №1", "Ref": "wh-1", "Number": "1", "TypeOfWarehouse": "branch"}
        ]
        total = _sync_warehouses_for_cities([city.pk])

    assert total == 1
    assert NovaPoshtaWarehouse.objects.filter(city=city, ref="wh-1").exists()


@pytest.mark.django_db
def test_enqueue_np_warehouse_sync_missing_only(settings):
    settings.NOVA_POSHTA_API_KEY = "test_key"
    synced = NovaPoshtaCity.objects.create(name="Київ", ref="kyiv-ref", area="Київська")
    pending = NovaPoshtaCity.objects.create(name="Львів", ref="lviv-ref", area="Львівська")
    NovaPoshtaWarehouse.objects.create(city=synced, name="№1", ref="wh-1", number="1")

    with patch("apps.integrations.novaposhta.tasks.sync_np_warehouses_chunk.delay") as delay:
        city_count, chunk_count = enqueue_np_warehouse_sync(missing_only=True)

    assert city_count == 1
    assert chunk_count == 1
    delay.assert_called_once_with([pending.pk])


@pytest.mark.django_db
def test_enqueue_np_warehouse_sync_splits_chunks(settings):
    settings.NOVA_POSHTA_API_KEY = "test_key"
    chunk_size = NP_WAREHOUSE_SYNC_CHUNK_SIZE
    for i in range(chunk_size + 1):
        NovaPoshtaCity.objects.create(name=f"City {i}", ref=f"ref-{i}", area="")

    with patch("apps.integrations.novaposhta.tasks.sync_np_warehouses_chunk.delay") as delay:
        city_count, chunk_count = enqueue_np_warehouse_sync(missing_only=False)

    assert city_count == chunk_size + 1
    assert chunk_count == 2
    assert delay.call_count == 2
