"""Fill English fields for service centre catalog."""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.services.i18n import (
    translate_category_name,
    translate_price_item_name,
    translate_service_description,
    translate_service_name,
)
from apps.services.models import PriceItem, Service, ServiceCategory


class Command(BaseCommand):
    help = "Backfill name_en / description_en for service centre categories, services, and prices."

    @transaction.atomic
    def handle(self, *args, **options):
        categories = 0
        services = 0
        prices = 0

        for category in ServiceCategory.objects.all():
            name_en = translate_category_name(category.name)
            if name_en and category.name_en != name_en:
                category.name_en = name_en
                category.save(update_fields=["name_en"])
                categories += 1

            for service in category.services.all():
                svc_en = translate_service_name(category.name, service.name)
                desc_en = translate_service_description(category.name)
                fields: list[str] = []
                if svc_en and service.name_en != svc_en:
                    service.name_en = svc_en
                    fields.append("name_en")
                if desc_en and service.description_en != desc_en:
                    service.description_en = desc_en
                    fields.append("description_en")
                if fields:
                    service.save(update_fields=fields)
                    services += 1

                for price in service.prices.all():
                    price_en = translate_price_item_name(price.name)
                    if price_en and price.name_en != price_en:
                        price.name_en = price_en
                        price.save(update_fields=["name_en"])
                        prices += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated categories={categories}, services={services}, price_items={prices}"
            )
        )
