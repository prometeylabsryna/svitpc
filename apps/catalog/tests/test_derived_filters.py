"""Derived facets (діагональ/CPU/RAM/відеокарта/SSD/колір) з ProductAttribute."""

import pytest

from apps.catalog.derived_filters import facet_rule_for_attribute_name, sync_derived_filters_for_product
from apps.catalog.models import Attribute, AttributeGroup, FilterGroup, ProductAttribute


class TestFacetRuleForAttributeName:
    @pytest.mark.parametrize(
        "name,expected_group",
        [
            ("Діагональ", "Діагональ"),
            ("Діагональ екрана", "Діагональ"),
            ("Серія процесора", "Серія процесора"),
            ("Модель процесора", "Серія процесора"),
            ("Оперативна пам'ять", "Оперативна пам'ять"),
            ("Об'єм оперативної пам'яті", "Оперативна пам'ять"),
            ("Модель відеокарти", "Модель відеокарти"),
            ("Об'єм SSD", "Об'єм SSD"),
            ("Колір", "Колір"),
            ("Колір корпусу", "Колір"),
        ],
    )
    def test_matches_expected_group(self, name, expected_group):
        rule = facet_rule_for_attribute_name(name)
        assert rule is not None
        assert rule.group_name == expected_group

    @pytest.mark.parametrize(
        "name",
        [
            "Максимальна підтримувана діагональ",
            "Мінімальна діагональ зображення",
            "Кількість ядер процесора",
            "Покоління процесора Intel",
            "Максимальний обсяг оперативної пам'яті",
            "Кількість роз'ємів оперативної пам'яті",
            "Колір тексту",
            "Виробник",
            "Гарантія, міс",
        ],
    )
    def test_excludes_unrelated_or_range_specs(self, name):
        assert facet_rule_for_attribute_name(name) is None

    def test_empty_name_returns_none(self):
        assert facet_rule_for_attribute_name("") is None
        assert facet_rule_for_attribute_name(None) is None


@pytest.mark.django_db
class TestSyncDerivedFiltersForProduct:
    def _add_attr(self, product, attr_name: str, value: str, group_name="Характеристики"):
        ag, _ = AttributeGroup.objects.get_or_create(name=group_name)
        attr, _ = Attribute.objects.get_or_create(group=ag, name=attr_name)
        ProductAttribute.objects.create(product=product, attribute=attr, value=value)

    def test_reuses_existing_filtergroup_by_exact_name(self, product_factory, filter_group_factory):
        existing_group = filter_group_factory(name="Діагональ")
        product = product_factory(slug="derived-diag-1")
        self._add_attr(product, "Діагональ", '15.6"')

        created = sync_derived_filters_for_product(product)

        assert created == 1
        assert FilterGroup.objects.filter(name="Діагональ").count() == 1
        pf = product.filters.select_related("filter__group").get()
        assert pf.filter.group_id == existing_group.pk
        assert pf.filter.name == '15.6"'

    def test_creates_group_when_missing(self, product_factory):
        product = product_factory(slug="derived-color-1")
        self._add_attr(product, "Колір", "Чорний")

        created = sync_derived_filters_for_product(product)

        assert created == 1
        assert FilterGroup.objects.filter(name="Колір").exists()

    def test_unmapped_attribute_ignored(self, product_factory):
        product = product_factory(slug="derived-unmapped-1")
        self._add_attr(product, "Гарантія, міс", "12")

        created = sync_derived_filters_for_product(product)

        assert created == 0
        assert product.filters.count() == 0

    def test_idempotent_no_duplicate_productfilter(self, product_factory):
        product = product_factory(slug="derived-idempotent-1")
        self._add_attr(product, "Об'єм SSD", "512 ГБ")

        first = sync_derived_filters_for_product(product)
        second = sync_derived_filters_for_product(product)

        assert first == 1
        assert second == 0
        assert product.filters.count() == 1

    def test_multiple_characteristics_map_to_distinct_groups(self, product_factory):
        product = product_factory(slug="derived-multi-1")
        self._add_attr(product, "Діагональ", '17.3"')
        self._add_attr(product, "Серія процесора", "Intel Core i5")
        self._add_attr(product, "Оперативна пам'ять", "16 ГБ")
        self._add_attr(product, "Модель відеокарти", "NVIDIA GeForce RTX 3050")
        self._add_attr(product, "Об'єм SSD", "512 ГБ")
        self._add_attr(product, "Колір", "Сірий")
        self._add_attr(product, "Виробник", "Test Brand")  # не мапиться — ігнорується

        created = sync_derived_filters_for_product(product)

        assert created == 6
        group_names = set(
            product.filters.select_related("filter__group").values_list("filter__group__name", flat=True),
        )
        assert group_names == {
            "Діагональ",
            "Серія процесора",
            "Оперативна пам'ять",
            "Модель відеокарти",
            "Об'єм SSD",
            "Колір",
        }

    def test_no_attributes_returns_zero(self, product_factory):
        product = product_factory(slug="derived-empty-1")
        assert sync_derived_filters_for_product(product) == 0

    def test_survives_duplicate_filter_rows_in_db(self, product_factory, filter_group_factory, filter_factory):
        """OpenCart-імпорт лишив 2 Filter з однаковим (group, name) — не має кидати MultipleObjectsReturned."""
        group = filter_group_factory(name="Діагональ")
        filter_factory(name='15.6"', group=group)
        filter_factory(name='15.6"', group=group)  # дублікат — прод-сценарій

        product = product_factory(slug="derived-dup-filter-1")
        self._add_attr(product, "Діагональ", '15.6"')

        created = sync_derived_filters_for_product(product)

        assert created == 1
        assert product.filters.count() == 1

    def test_survives_duplicate_filtergroup_rows_in_db(self, product_factory, filter_group_factory):
        """2 FilterGroup з однаковою назвою (дубль з імпорту) — не має кидати MultipleObjectsReturned."""
        filter_group_factory(name="Колір")
        filter_group_factory(name="Колір")  # дублікат — прод-сценарій

        product = product_factory(slug="derived-dup-group-1")
        self._add_attr(product, "Колір", "Чорний")

        created = sync_derived_filters_for_product(product)

        assert created == 1
        assert product.filters.count() == 1
