from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.integrations.vchasnokasa.client import VchasnoKasaClient
from apps.orders.models import Order


class Command(BaseCommand):
    help = "Перевірити підключення до Вчасно.Каса або фіскалізувати замовлення"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--order-id",
            type=int,
            help="ID замовлення для тестової фіскалізації",
        )
        parser.add_argument(
            "--ping",
            action="store_true",
            help="Лише перевірити токен каси (статус ПРРО)",
        )

    def handle(self, *args, **options) -> None:
        client = VchasnoKasaClient()
        if not client.is_configured():
            raise CommandError("VCHASNO_CASHBOX_KEY не задано в .env")

        if options["ping"] or not options["order_id"]:
            if client.ping():
                self.stdout.write(self.style.SUCCESS("Vchasno.Kasa: підключення OK"))
            else:
                raise CommandError("Vchasno.Kasa: помилка підключення (перевірте токен каси)")
            return

        order = Order.objects.filter(pk=options["order_id"]).prefetch_related("items").first()
        if not order:
            raise CommandError(f"Замовлення #{options['order_id']} не знайдено")
        if order.fiscal_check_url:
            self.stdout.write(f"Замовлення #{order.pk} вже має чек: {order.fiscal_check_url}")
            return

        url = client.create_receipt(order)
        if not url:
            raise CommandError(f"Не вдалося створити чек для замовлення #{order.pk}")
        Order.objects.filter(pk=order.pk).update(fiscal_check_url=url)
        self.stdout.write(self.style.SUCCESS(f"Чек створено: {url}"))
