import pytest
from django.utils import translation

from apps.core.glossary_uk_en import localize_uk_to_en
from apps.core.i18n import localized_field


def test_localize_uk_to_en_glossary() -> None:
    assert localize_uk_to_en("Країна виробництва") == "Country of manufacture"
    assert localize_uk_to_en("Laptop") == "Laptop"


@pytest.mark.django_db
def test_localized_field_uses_glossary_when_en_missing() -> None:
    from apps.catalog.models import FilterGroup

    group = FilterGroup.objects.create(name="Країна виробництва", name_uk="Країна виробництва")
    with translation.override("en"):
        assert localized_field(group, "name") == "Country of manufacture"
