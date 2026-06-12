"""Service centre i18n tests."""

from django.test import TestCase

from apps.services.i18n import (
    translate_category_name,
    translate_price_item_name,
    translate_service_description,
    translate_service_name,
    translate_unit,
)


class ServiceI18nTests(TestCase):
    def test_category_and_service_translations(self):
        assert translate_category_name("Ноутбуки") == "Laptops"
        assert translate_service_name("Ноутбуки", "Ремонт ноутбуків") == "Laptop repair"
        assert "Diagnostics" in translate_service_description("Ноутбуки")

    def test_price_item_translation(self):
        assert translate_price_item_name("Заміна Матриці Ноутбука") == "Laptop screen replacement"

    def test_unit_translation(self):
        assert translate_unit("шт") == "pc"
