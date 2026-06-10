import pytest
from django.core.cache import cache

from apps.catalog.nav import NAV_ORDER_CACHE_KEY, get_top_categories
from apps.catalog.models import Category


@pytest.fixture(autouse=True)
def clear_nav_cache():
    cache.delete(NAV_ORDER_CACHE_KEY)
    yield
    cache.delete(NAV_ORDER_CACHE_KEY)


@pytest.mark.django_db
class TestCatalogNav:
    def test_prefetches_active_children(self, category_factory):
        parent = category_factory(name="Parent", slug="parent-nav", is_top=True)
        Category.objects.create(name="Child Active", slug="child-active", parent=parent, is_active=True)
        Category.objects.create(name="Child Hidden", slug="child-hidden", parent=parent, is_active=False)

        top = get_top_categories()
        parent_cat = next(c for c in top if c.slug == "parent-nav")
        child_names = [c.name for c in parent_cat.children.all()]
        assert child_names == ["Child Active"]

    def test_empty_categories_move_to_bottom(
        self, category_factory, product_factory,
    ):
        empty = category_factory(name="Empty", slug="empty-nav", is_top=True, sort_order=1)
        filled = category_factory(name="Filled", slug="filled-nav", is_top=True, sort_order=2)
        product = product_factory(slug="nav-product")
        product.categories.add(filled)

        slugs = [c.slug for c in get_top_categories()]
        assert slugs.index("filled-nav") < slugs.index("empty-nav")

    def test_empty_child_categories_move_to_bottom(
        self, category_factory, product_factory,
    ):
        parent = category_factory(name="Parent", slug="parent-sort", is_top=True)
        empty_child = Category.objects.create(
            name="Empty Child", slug="empty-child", parent=parent, is_active=True, sort_order=1,
        )
        filled_child = Category.objects.create(
            name="Filled Child", slug="filled-child", parent=parent, is_active=True, sort_order=2,
        )
        product = product_factory(slug="child-product")
        product.categories.add(filled_child)

        parent_cat = next(c for c in get_top_categories() if c.slug == "parent-sort")
        child_slugs = [c.slug for c in parent_cat.children.all()]
        assert child_slugs == ["filled-child", "empty-child"]
