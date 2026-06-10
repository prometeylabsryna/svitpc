import pytest

from apps.catalog.search_index import refresh_product_search_vectors
from apps.catalog.models import Product


@pytest.mark.django_db
def test_refresh_product_search_vector(product_factory):
    product = product_factory(name="Indexed Widget", sku="IDX-1", slug="idx-1")
    assert product.search_vector is None

    refresh_product_search_vectors(Product.objects.filter(pk=product.pk))

    product.refresh_from_db()
    assert product.search_vector is not None
