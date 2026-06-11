"""Sync Nova Poshta cities and warehouses into local DB."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Download Nova Poshta cities and warehouses (requires NOVA_POSHTA_API_KEY)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cities-only",
            action="store_true",
            help="Sync cities without warehouses",
        )
        parser.add_argument(
            "--warehouses-only",
            action="store_true",
            help="Sync warehouses without refreshing cities",
        )
        parser.add_argument(
            "--missing-only",
            action="store_true",
            help="Sync warehouses only for cities with none in DB yet",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            dest="use_celery",
            help="Enqueue Celery tasks instead of running synchronously",
        )

    def handle(self, *args, **options):
        from apps.integrations.novaposhta.tasks import (
            NP_WAREHOUSE_SYNC_CHUNK_SIZE,
            _sync_warehouses_for_cities,
            enqueue_np_warehouse_sync,
            sync_np_cities,
        )

        warehouses_only = options["warehouses_only"]
        missing_only = options["missing_only"]

        if options["use_celery"]:
            if not warehouses_only:
                sync_np_cities.delay()
            if not options["cities_only"]:
                city_count, chunk_count = enqueue_np_warehouse_sync(missing_only=missing_only)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Enqueued {chunk_count} warehouse chunks "
                        f"({city_count} cities, chunk size {NP_WAREHOUSE_SYNC_CHUNK_SIZE})."
                    )
                )
            elif warehouses_only:
                self.stdout.write(self.style.SUCCESS("Nova Poshta city sync skipped."))
            else:
                self.stdout.write(self.style.SUCCESS("Nova Poshta sync tasks enqueued."))
            return

        if not warehouses_only:
            client_msg = sync_np_cities()
            self.stdout.write(self.style.SUCCESS(str(client_msg)))

        if options["cities_only"]:
            return

        from django.db.models import Count

        from apps.shipping.models import NovaPoshtaCity

        qs = NovaPoshtaCity.objects.order_by("pk")
        if missing_only:
            qs = qs.annotate(_wh_count=Count("warehouses")).filter(_wh_count=0)

        city_ids = list(qs.values_list("pk", flat=True))
        total_wh = 0
        for offset in range(0, len(city_ids), NP_WAREHOUSE_SYNC_CHUNK_SIZE):
            chunk = city_ids[offset : offset + NP_WAREHOUSE_SYNC_CHUNK_SIZE]
            chunk_total = _sync_warehouses_for_cities(chunk)
            total_wh += chunk_total
            self.stdout.write(
                self.style.SUCCESS(
                    f"Synced {chunk_total} warehouses for {len(chunk)} cities "
                    f"({offset + len(chunk)}/{len(city_ids)})."
                )
            )

        self.stdout.write(self.style.SUCCESS(f"Done: {total_wh} warehouses across {len(city_ids)} cities."))
