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
    def test_prefetches_active_children(self, category_factory, product_factory):
        parent = category_factory(name="Parent", slug="parent-nav", is_top=True)
        active_child = Category.objects.create(
            name="Child Active", slug="child-active", parent=parent, is_active=True,
        )
        Category.objects.create(name="Child Hidden", slug="child-hidden", parent=parent, is_active=False)
        product = product_factory(slug="nav-active-child-product")
        product.categories.add(active_child)

        top = get_top_categories()
        parent_cat = next(c for c in top if c.slug == "parent-nav")
        child_names = [c.name for c in parent_cat.children.all()]
        assert child_names == ["Child Active"]

    def test_empty_categories_hidden_from_nav(
        self, category_factory, product_factory,
    ):
        empty = category_factory(name="Empty", slug="empty-nav", is_top=True, sort_order=1)
        filled = category_factory(name="Filled", slug="filled-nav", is_top=True, sort_order=2)
        product = product_factory(slug="nav-product")
        product.categories.add(filled)

        slugs = [c.slug for c in get_top_categories()]
        assert "empty-nav" not in slugs
        assert "filled-nav" in slugs

    def test_empty_child_categories_hidden_from_nav(
        self, category_factory, product_factory,
    ):
        parent = category_factory(name="Parent", slug="parent-sort", is_top=True)
        Category.objects.create(
            name="Empty Child", slug="empty-child", parent=parent, is_active=True, sort_order=1,
        )
        filled_child = Category.objects.create(
            name="Filled Child", slug="filled-child", parent=parent, is_active=True, sort_order=2,
        )
        product = product_factory(slug="child-product")
        product.categories.add(filled_child)

        parent_cat = next(c for c in get_top_categories() if c.slug == "parent-sort")
        child_slugs = [c.slug for c in parent_cat.children.all()]
        assert child_slugs == ["filled-child"]

    def test_top_category_hidden_when_only_empty_children(
        self, category_factory,
    ):
        """A top category with zero products anywhere in its subtree disappears entirely."""
        parent = category_factory(name="Ghost", slug="ghost-nav", is_top=True)
        Category.objects.create(name="Ghost Child", slug="ghost-child", parent=parent, is_active=True)

        slugs = [c.slug for c in get_top_categories()]
        assert "ghost-nav" not in slugs

    def test_adding_product_to_previously_empty_category_refreshes_nav(
        self, category_factory, product_factory,
    ):
        """Regression: адмін вручну додає перший товар у порожню категорію
        (напр. «Б/У») — вона має з'явитись у навігації без очікування TTL,
        навіть якщо nav-кеш вже прогрітий зі старим (порожнім) станом."""
        used = category_factory(name="Б/У", slug="бу-nav", is_top=True)
        product = product_factory(slug="bu-first-product")

        # Прогріваємо кеш ДО того, як товар потрапить у категорію — категорія
        # ще порожня і не потрапить у payload.
        slugs_before = [c.slug for c in get_top_categories()]
        assert "бу-nav" not in slugs_before

        product.categories.add(used)  # мімікрує ProductAdmin: form.save_m2m()

        slugs_after = [c.slug for c in get_top_categories()]
        assert "бу-nav" in slugs_after

    def test_saving_existing_product_refreshes_nav(self, category_factory, product_factory):
        """Зміна вже прив'язаного товару (напр. is_visible) також скидає nav-кеш."""
        cat = category_factory(name="Filled", slug="filled-save-nav", is_top=True)
        product = product_factory(slug="save-nav-product", is_visible=False)
        product.categories.add(cat)

        slugs_before = [c.slug for c in get_top_categories()]
        assert "filled-save-nav" not in slugs_before

        product.is_visible = True
        product.save()

        slugs_after = [c.slug for c in get_top_categories()]
        assert "filled-save-nav" in slugs_after

    def test_nav_not_invalidated_during_heavy_sync(self, category_factory, product_factory):
        """Під час важкого синку сигнал не скидає nav — синк сам зробить це
        одноразово у finally (див. heavy_catalog_sync_lock)."""
        from django.core.cache import cache as django_cache

        from apps.integrations.heavy_sync import LOCK_KEY

        used = category_factory(name="Б/У", slug="бу-heavy-nav", is_top=True)
        product = product_factory(slug="bu-heavy-product")

        get_top_categories()  # прогріти кеш без категорії
        django_cache.set(LOCK_KEY, "test-heavy-sync", 3600)
        try:
            product.categories.add(used)
            cached = django_cache.get(NAV_ORDER_CACHE_KEY)
            assert cached is not None  # кеш лишився старим (не скинутий сигналом)
        finally:
            django_cache.delete(LOCK_KEY)

    def test_invalidate_nav_cache_clears_template_fragment(
        self, settings,
    ):
        from django.core.cache.utils import make_template_fragment_key

        from apps.catalog.nav import NAV_TEMPLATE_FRAGMENT, invalidate_nav_cache

        settings.LANGUAGES = [("uk", "Ukrainian"), ("en", "English")]
        for lang, _ in settings.LANGUAGES:
            key = make_template_fragment_key(NAV_TEMPLATE_FRAGMENT, [lang])
            cache.set(key, "<nav>stale</nav>", 600)

        invalidate_nav_cache()

        for lang, _ in settings.LANGUAGES:
            key = make_template_fragment_key(NAV_TEMPLATE_FRAGMENT, [lang])
            assert cache.get(key) is None
