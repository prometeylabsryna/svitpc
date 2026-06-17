"""Diagnose Nova Poshta TTN creation for an order."""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.integrations.novaposhta.client import NovaPoshtaClient
from apps.orders.models import Order


class Command(BaseCommand):
    help = "Перевірити налаштування НП і спробувати створити ТТН для замовлення"

    def add_arguments(self, parser):
        parser.add_argument("--order-id", type=int, required=True, help="ID замовлення")

    def handle(self, *args, **options):
        order_id = options["order_id"]
        try:
            order = Order.objects.prefetch_related("items__product").get(pk=order_id)
        except Order.DoesNotExist as exc:
            raise CommandError(f"Замовлення #{order_id} не знайдено") from exc

        self.stdout.write(f"Замовлення #{order.pk}: {order.delivery_type}, оплата={order.payment_method}")
        self.stdout.write(f"  city={order.city!r} city_ref={order.city_ref!r}")
        self.stdout.write(f"  warehouse={order.warehouse!r} warehouse_ref={order.warehouse_ref!r}")
        self.stdout.write(f"  ttn={order.ttn!r}")

        sender_ok = all(
            [
                settings.NOVA_POSHTA_API_KEY,
                settings.NP_SENDER_REF,
                settings.NP_SENDER_CONTACT_REF,
                settings.NP_SENDER_PHONE,
                settings.NP_SENDER_CITY_REF,
                settings.NP_SENDER_WAREHOUSE_REF,
            ]
        )
        if not sender_ok:
            self.stdout.write(self.style.ERROR("NP_SENDER_* або API key порожні в налаштуваннях процесу"))
        else:
            self.stdout.write(self.style.SUCCESS("NP_SENDER_* і API key присутні"))

        if order.ttn:
            self.stdout.write(self.style.WARNING("ТТН вже є — новий не створюється"))
            return

        client = NovaPoshtaClient()
        ttn, error = client.create_ttn(order)
        if ttn:
            order.ttn = ttn
            order.save(update_fields=["ttn"])
            self.stdout.write(self.style.SUCCESS(f"ТТН створено: {ttn}"))
            return

        self.stdout.write(self.style.ERROR(f"Помилка: {error or 'невідома'}"))
