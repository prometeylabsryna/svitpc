"""Management command for manual Kancmaster XML synchronization."""

from django.core.management.base import BaseCommand

from apps.integrations.kancmaster.tasks import sync_all


class Command(BaseCommand):
    help = "Synchronise products from Kancmaster XML feed (runs synchronously)."

    def handle(self, *args, **options) -> None:
        self.stdout.write("Starting Kancmaster XML sync…")
        sync_all()
        self.stdout.write(self.style.SUCCESS("Kancmaster sync finished."))
