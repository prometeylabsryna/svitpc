from celery import shared_task


@shared_task
def sync_np_cities():
    """Download/refresh Nova Poshta city list."""
    from .client import NovaPoshtaClient
    client = NovaPoshtaClient()
    count = client.sync_cities_to_db()
    return f"Synced {count} cities"


@shared_task
def sync_np_warehouses():
    """Download/refresh Nova Poshta warehouse list for all cities in DB."""
    from apps.shipping.models import NovaPoshtaCity, NovaPoshtaWarehouse
    from .client import NovaPoshtaClient

    client = NovaPoshtaClient()
    total = 0
    for city in NovaPoshtaCity.objects.all():
        warehouses = client.get_warehouses(city.ref)
        objs = [
            NovaPoshtaWarehouse(
                city=city,
                name=w.get("Description", ""),
                ref=w["Ref"],
                number=w.get("Number", ""),
                type=w.get("TypeOfWarehouse", ""),
            )
            for w in warehouses if w.get("Ref")
        ]
        NovaPoshtaWarehouse.objects.bulk_create(
            objs,
            update_conflicts=True,
            update_fields=["name", "number", "type"],
            unique_fields=["ref"],
        )
        total += len(objs)
    return f"Synced {total} warehouses"
