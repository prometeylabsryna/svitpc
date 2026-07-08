"""Регресійні перевірки SQL-бюджету гарячих шляхів каталогу."""

from __future__ import annotations

import pytest

from apps.catalog.nav import get_top_categories
from apps.catalog.services import visible_catalog_products


@pytest.mark.django_db
def test_nav_warm_path_zero_queries(category_factory, django_assert_num_queries):
    """Warm nav — 0 SQL: повний payload категорій сервірується з кешу."""
    parent = category_factory(name="Top", slug="perf-top", is_top=True)
    category_factory(name="Child", slug="perf-child", parent=parent)

    get_top_categories()  # cache miss — будує payload

    with django_assert_num_queries(0):
        result = get_top_categories()
        # Діти теж без SQL (prefetch у payload)
        for cat in result:
            list(cat.children.all())

    assert any(c.slug == "perf-top" for c in result)


@pytest.mark.django_db
def test_visible_catalog_products_no_gallery_exists():
    """Листинги фільтрують фото денормалізованим прапорцем, без EXISTS по галереї."""
    sql = str(visible_catalog_products().query)
    assert "has_display_image" in sql
    assert "catalog_productimage" not in sql  # EXISTS-предикат прибрано з гарячого шляху


@pytest.mark.django_db
def test_category_page_warm_query_budget(
    client, category_factory, product_factory, django_assert_max_num_queries,
):
    """Сторінка категорії на warm cache — не більше 12 SQL (було 12–16 на побудові
    двох queryset і EXISTS-предикаті)."""
    category = category_factory(name="Perf Cat", slug="perf-cat", is_top=True)
    for i in range(3):
        product = product_factory(slug=f"perf-item-{i}")
        product.categories.add(category)

    # Прогрів: nav, facets, counts, site settings
    assert client.get(f"/category/{category.slug}/").status_code == 200

    with django_assert_max_num_queries(12):
        response = client.get(f"/category/{category.slug}/")
    assert response.status_code == 200
