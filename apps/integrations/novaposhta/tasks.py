from celery import shared_task

from .client import NovaPoshtaClient

NP_WAREHOUSE_SYNC_CHUNK_SIZE = 75


def _sync_warehouses_for_cities(city_pks: list[int]) -> int:
    from apps.shipping.models import NovaPoshtaCity, NovaPoshtaWarehouse

    client = NovaPoshtaClient()
    total = 0
    for city in NovaPoshtaCity.objects.filter(pk__in=city_pks).iterator():
        warehouses = client.get_warehouses(city.ref)
        objs = [
            NovaPoshtaWarehouse(
                city=city,
                name=w.get("Description", ""),
                ref=w["Ref"],
                number=w.get("Number", ""),
                type=w.get("TypeOfWarehouse", ""),
            )
            for w in warehouses
            if w.get("Ref")
        ]
        if objs:
            NovaPoshtaWarehouse.objects.bulk_create(
                objs,
                update_conflicts=True,
                update_fields=["name", "number", "type"],
                unique_fields=["ref"],
            )
        total += len(objs)
    return total


def enqueue_np_warehouse_sync(*, missing_only: bool = False) -> tuple[int, int]:
    """Enqueue Celery chunks; returns (city_count, chunk_count)."""
    from django.db.models import Count

    from apps.shipping.models import NovaPoshtaCity

    qs = NovaPoshtaCity.objects.order_by("pk")
    if missing_only:
        qs = qs.annotate(_wh_count=Count("warehouses")).filter(_wh_count=0)

    city_ids = list(qs.values_list("pk", flat=True))
    chunk_count = 0
    for offset in range(0, len(city_ids), NP_WAREHOUSE_SYNC_CHUNK_SIZE):
        chunk = city_ids[offset : offset + NP_WAREHOUSE_SYNC_CHUNK_SIZE]
        sync_np_warehouses_chunk.delay(chunk)
        chunk_count += 1
    return len(city_ids), chunk_count


@shared_task
def sync_np_cities():
    """Download/refresh Nova Poshta city list."""
    client = NovaPoshtaClient()
    count = client.sync_cities_to_db()
    return f"Synced {count} cities"


@shared_task
def sync_np_warehouses_chunk(city_pks: list[int]):
    """Sync NP warehouses for a batch of cities (memory-safe)."""
    total = _sync_warehouses_for_cities(city_pks)
    return f"Synced {total} warehouses for {len(city_pks)} cities"


@shared_task
def sync_np_warehouses():
    """Enqueue warehouse sync in chunks for all cities in DB."""
    city_count, chunk_count = enqueue_np_warehouse_sync(missing_only=False)
    return f"Enqueued {chunk_count} chunks for {city_count} cities"
