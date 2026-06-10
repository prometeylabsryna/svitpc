import pytest
from django.utils.text import slugify


@pytest.mark.django_db
class TestBrand:
    def test_brand_slug_auto(self, brand_factory):
        # Pass explicit slug="" to trigger auto-generation from name
        brand = brand_factory(name="Apple Inc", slug="")
        assert brand.slug == slugify("Apple Inc", allow_unicode=True)

    def test_brand_str(self, brand_factory):
        brand = brand_factory(name="Samsung")
        assert str(brand) == "Samsung"


@pytest.mark.django_db
class TestProduct:
    def test_product_is_available(self, product_factory):
        p = product_factory(stock=5)
        assert p.is_available

    def test_product_unavailable_zero_stock(self, product_factory):
        p = product_factory(stock=0)
        assert not p.is_available

    def test_product_url(self, product_factory):
        p = product_factory()
        assert p.get_absolute_url().startswith("/")

    def test_product_cyrillic_slug_passes_validation(self, product_factory):
        slug = "3d-пазл-1в-951101-екскаватор-1120"
        p = product_factory(name='3D Пазл "1В"', slug=slug)
        p.full_clean()
        assert p.slug == slug
