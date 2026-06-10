import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.catalog.nav import NAV_ORDER_CACHE_KEY, get_top_categories
from apps.core.models import SiteSettings


@pytest.fixture(autouse=True)
def clear_nav_cache():
    cache.delete(NAV_ORDER_CACHE_KEY)
    yield
    cache.delete(NAV_ORDER_CACHE_KEY)


@pytest.mark.django_db
class TestUsedCategoryVisibility:
    def test_hidden_from_nav_when_disabled(self, category_factory):
        used = category_factory(name="Б/У", slug="bu-test", is_top=True)
        visible = category_factory(name="Laptops", slug="laptops-test", is_top=True)

        site = SiteSettings.load()
        site.used_category = used
        site.show_used_category = False
        site.save()

        slugs = [c.slug for c in get_top_categories()]
        assert "bu-test" not in slugs
        assert "laptops-test" in slugs

    def test_shown_in_nav_when_enabled(self, category_factory):
        used = category_factory(name="Б/У", slug="bu-visible", is_top=True)

        site = SiteSettings.load()
        site.used_category = used
        site.show_used_category = True
        site.save()

        slugs = [c.slug for c in get_top_categories()]
        assert "bu-visible" in slugs

    def test_category_page_404_when_disabled(self, client, category_factory):
        used = category_factory(name="Б/У", slug="bu-hidden-page", is_top=True)

        site = SiteSettings.load()
        site.used_category = used
        site.show_used_category = False
        site.save()

        response = client.get(reverse("catalog:category", kwargs={"slug": used.slug}))
        assert response.status_code == 404

    def test_subcategory_page_404_when_disabled(self, client, category_factory):
        used = category_factory(name="Б/У", slug="bu-root", is_top=True)
        child = category_factory(name="Ноутбуки Б/У", slug="bu-laptops", parent=used, is_top=False)

        site = SiteSettings.load()
        site.used_category = used
        site.show_used_category = False
        site.save()

        response = client.get(reverse("catalog:category", kwargs={"slug": child.slug}))
        assert response.status_code == 404

    def test_category_page_ok_when_enabled(self, client, category_factory):
        used = category_factory(name="Б/У", slug="bu-open", is_top=True)

        site = SiteSettings.load()
        site.used_category = used
        site.show_used_category = True
        site.save()

        response = client.get(reverse("catalog:category", kwargs={"slug": used.slug}))
        assert response.status_code == 200
