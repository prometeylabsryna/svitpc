import pytest
from django.utils import translation

from apps.catalog.services import get_product_facets


@pytest.mark.django_db
def test_facets_use_english_group_names(
    product_factory, filter_group_factory, filter_factory, product_filter_factory,
) -> None:
    group = filter_group_factory(name="Країна виробництва", name_uk="Країна виробництва")
    filt = filter_factory(name="Україна", group=group, name_uk="Україна")
    product = product_factory()
    product_filter_factory(product, filt)

    qs = type(product).objects.filter(pk=product.pk)
    with translation.override("en"):
        facets = get_product_facets(qs)
    names = [g["name"] for g in facets.values()]
    assert "Country of manufacture" in names
