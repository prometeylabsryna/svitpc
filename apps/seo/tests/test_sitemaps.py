"""Tests for apps.seo.sitemaps — items() must match what actually resolves (не 404)."""

from __future__ import annotations

import pytest

from apps.catalog.models import Product
from apps.seo.sitemaps import CategorySitemap


@pytest.mark.django_db
class TestCategorySitemap:
    def test_excludes_category_without_visible_products(
        self, category_factory, product_factory,
    ):
        """Регресія: sitemap раніше містив ВСІ активні категорії, навіть ті,
        що category_view ховає (404) через відсутність товарів у піддереві —
        тисячі мертвих посилань, які Google отримував через офіційний sitemap."""
        empty_cat = category_factory(name="Порожня категорія", slug="empty-cat")
        populated_cat = category_factory(name="З товарами", slug="populated-cat")
        product = product_factory(slug="in-populated-cat", is_visible=True)
        product.categories.add(populated_cat)

        items = CategorySitemap().items()

        assert populated_cat in items
        assert empty_cat not in items

    def test_includes_category_with_only_subcategory_products(
        self, category_factory, product_factory,
    ):
        """Батьківська категорія без прямих товарів, але з товарами в
        підкатегорії — теж реально відкривається (category_view рахує
        піддерево), тож теж має лишитись у sitemap."""
        parent = category_factory(name="Батько", slug="parent-cat")
        child = category_factory(name="Дитина", slug="child-cat", parent=parent)
        product = product_factory(slug="in-child-cat", is_visible=True)
        product.categories.add(child)

        items = CategorySitemap().items()

        assert parent in items
        assert child in items

    def test_hidden_products_do_not_count(self, category_factory, product_factory):
        cat = category_factory(name="Тільки приховані", slug="hidden-only-cat")
        product = product_factory(slug="hidden-product", is_visible=False)
        product.categories.add(cat)

        items = CategorySitemap().items()

        assert cat not in items

    def test_kancmaster_and_manual_categories_not_special_cased(
        self, category_factory, product_factory,
    ):
        """Фільтр НЕ повинен бути прив'язаний до Brain-вайтліста категорій —
        Kancmaster/manual категорії з реальними товарами мають лишатись
        у sitemap так само, як і Brain."""
        used_cat = category_factory(name="Б/У ноутбуки", slug="used-laptops")
        used_product = product_factory(
            slug="used-laptop-1", is_visible=True, source=Product.SOURCE_MANUAL,
        )
        used_product.categories.add(used_cat)

        items = CategorySitemap().items()

        assert used_cat in items

    def test_excludes_hidden_used_category_branch(
        self, category_factory, product_factory, settings,
    ):
        """`is_used_category_branch` теж ховає сторінку (404) — sitemap має
        це врахувати, навіть якщо в гілці є товари."""
        from apps.core.models import SiteSettings
        from apps.core.used_category import invalidate_hidden_used_category_cache

        used_root = category_factory(name="Б/У", slug="used-root")
        product = product_factory(slug="used-hidden-product", is_visible=True)
        product.categories.add(used_root)

        site = SiteSettings.load()
        site.used_category_id = used_root.pk
        site.show_used_category = False
        site.save()
        invalidate_hidden_used_category_cache()

        try:
            items = CategorySitemap().items()
            assert used_root not in items
        finally:
            site.show_used_category = True
            site.save()
            invalidate_hidden_used_category_cache()
