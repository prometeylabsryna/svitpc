"""Brain content-sync і Kancmaster attribute-sync мають наповнювати ProductFilter (фасети)."""

from decimal import Decimal

import pytest

from apps.catalog.models import FilterGroup, Product


@pytest.mark.django_db
class TestBrainContentSyncDerivedFilters:
    def test_sync_options_from_detail_creates_productfilter(self):
        from apps.integrations.brain.content_sync import sync_options_from_detail

        product = Product.objects.create(
            source=Product.SOURCE_BRAIN,
            external_id="777001",
            name="Ноутбук тест",
            slug="derived-brain-777001",
            price=Decimal("20000"),
            stock=1,
        )
        detail = {
            "options": [
                {"OptionName": "Диагональ", "ValueName": '15.6"'},  # RU → UK через глосарій
                {"OptionName": "Об'єм SSD", "ValueName": "512 ГБ"},
                {"OptionName": "Гарантія, міс", "ValueName": "12"},  # не мапиться у фасет
            ],
        }

        written = sync_options_from_detail(product, detail)

        assert written == 3
        group_names = set(
            product.filters.select_related("filter__group").values_list("filter__group__name", flat=True),
        )
        assert group_names == {"Діагональ", "Об'єм SSD"}


@pytest.mark.django_db
class TestKancmasterAttributesDerivedFilters:
    def test_sync_product_attributes_creates_productfilter(self):
        from apps.integrations.kancmaster.attributes import sync_product_attributes

        product = Product.objects.create(
            source=Product.SOURCE_KANCMASTER,
            external_id="km-777002",
            name="Товар тест",
            slug="derived-kancmaster-777002",
            price=Decimal("500"),
            stock=1,
        )
        params = [
            {"name": "Цвет", "value": "Чорний"},  # RU → UK через глосарій
            {"name": "Оперативна пам'ять", "value": "16 ГБ"},
        ]

        written = sync_product_attributes(product, params)

        assert written == 2
        assert FilterGroup.objects.filter(name="Колір").exists()
        group_names = set(
            product.filters.select_related("filter__group").values_list("filter__group__name", flat=True),
        )
        assert group_names == {"Колір", "Оперативна пам'ять"}
