import pytest

from apps.catalog.models import Filter, FilterGroup, ProductAttribute, ProductFilter
from apps.catalog.services import get_product_facets
from apps.catalog.spec_filters import (
    resolve_spec_group,
    sync_spec_filters_from_attributes,
    sync_spec_filters_from_options,
)


@pytest.mark.parametrize(
    "option_name,expected",
    [
        ("Діагональ екрану", "Діагональ"),
        ("Процесор", "Процесор"),
        ("Обсяг оперативної пам'яті", "Оперативна пам'ять"),
        ("Відеокарта", "Відеокарта"),
        ("Обсяг накопичувача SSD", "SSD"),
        ("Колір корпусу", "Колір"),
        ("Гарантія", None),
    ],
)
def test_resolve_spec_group(option_name, expected):
    assert resolve_spec_group(option_name) == expected


@pytest.mark.django_db
class TestSpecFilterSync:
    def test_sync_creates_filters_and_facets(self, product_factory):
        product = product_factory(image_url="https://cdn.example.com/p.jpg")
        options = [
            {"OptionName": "Процесор", "ValueName": "Intel Core i5"},
            {"OptionName": "Діагональ екрану", "ValueName": '15.6"'},
            {"OptionName": "Гарантія", "ValueName": "12 міс."},
        ]
        sync_spec_filters_from_options(product, options)

        assert ProductFilter.objects.filter(product=product).count() == 2
        assert FilterGroup.objects.filter(name="Процесор").exists()
        assert Filter.objects.filter(name="Intel Core i5").exists()

        facets = get_product_facets(type(product).objects.filter(pk=product.pk))
        names = [group["name"] for group in facets.values()]
        assert "Процесор" in names
        assert "Діагональ" in names

    def test_sync_from_attributes(self, product_factory):
        from apps.catalog.models import Attribute, AttributeGroup

        product = product_factory(image_url="https://cdn.example.com/p.jpg")
        group = AttributeGroup.objects.create(name="Характеристики")
        ram = Attribute.objects.create(group=group, name="Обсяг оперативної пам'яті")
        color = Attribute.objects.create(group=group, name="Колір")
        ProductAttribute.objects.create(product=product, attribute=ram, value="16 ГБ")
        ProductAttribute.objects.create(product=product, attribute=color, value="Сірий")

        sync_spec_filters_from_attributes(product)

        linked = set(
            ProductFilter.objects.filter(product=product).values_list("filter__name", flat=True)
        )
        assert linked == {"16 ГБ", "Сірий"}

    def test_duplicate_filter_groups_same_name(self, product_factory):
        FilterGroup.objects.create(name="Колір", sort_order=99)
        FilterGroup.objects.create(name="Колір", sort_order=99)
        product = product_factory(image_url="https://cdn.example.com/p.jpg")
        sync_spec_filters_from_options(
            product,
            [{"OptionName": "Колір", "ValueName": "Чорний"}],
        )
        assert ProductFilter.objects.filter(product=product).count() == 1

    def test_resync_replaces_old_spec_values(self, product_factory):
        product = product_factory(image_url="https://cdn.example.com/p.jpg")
        sync_spec_filters_from_options(
            product,
            [{"OptionName": "Процесор", "ValueName": "Intel Core i5"}],
        )
        sync_spec_filters_from_options(
            product,
            [{"OptionName": "Процесор", "ValueName": "Intel Core i7"}],
        )
        names = list(
            ProductFilter.objects.filter(product=product).values_list("filter__name", flat=True)
        )
        assert names == ["Intel Core i7"]

    def test_priority_facets_flag(self, product_factory):
        product = product_factory(image_url="https://cdn.example.com/p.jpg")
        sync_spec_filters_from_options(
            product,
            [{"OptionName": "Колір", "ValueName": "Чорний"}],
        )
        facets = get_product_facets(type(product).objects.filter(pk=product.pk))
        assert any(group.get("is_priority") for group in facets.values())
