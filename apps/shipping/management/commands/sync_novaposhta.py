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
            "--async",
            action="store_true",
            dest="use_celery",
            help="Enqueue Celery tasks instead of running synchronously",
        )

    def handle(self, *args, **options):
        from apps.integrations.novaposhta.tasks import sync_np_cities, sync_np_warehouses

        if options["use_celery"]:
            sync_np_cities.delay()
            if not options["cities_only"]:
                sync_np_warehouses.delay()
            self.stdout.write(self.style.SUCCESS("Nova Poshta sync tasks enqueued."))
            return

        client_msg = sync_np_cities()
        self.stdout.write(self.style.SUCCESS(str(client_msg)))
        if not options["cities_only"]:
            wh_msg = sync_np_warehouses()
            self.stdout.write(self.style.SUCCESS(str(wh_msg)))
