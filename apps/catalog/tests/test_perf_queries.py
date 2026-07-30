"""Регресійні перевірки SQL-бюджету гарячих шляхів каталогу."""

from __future__ import annotations

import pytest

from apps.catalog.nav import get_top_categories
from apps.catalog.services import visible_catalog_products


@pytest.mark.django_db
def test_nav_warm_path_zero_queries(category_factory, product_factory, django_assert_num_queries):
    """Warm nav — 0 SQL: повний payload категорій сервірується з кешу."""
    parent = category_factory(name="Top", slug="perf-top", is_top=True)
    child = category_factory(name="Child", slug="perf-child", parent=parent)
    product = product_factory(slug="perf-nav-product")
    product.categories.add(child)

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


@pytest.mark.django_db
def test_disjunctive_facets_query_budget_independent_of_group_count(
    product_factory, filter_group_factory, filter_factory, product_filter_factory,
    django_assert_max_num_queries,
):
    """SQL для get_disjunctive_facets має рости з кількістю ВИБРАНИХ груп, а не з
    кількістю фасетних груп у категорії — інакше кожен клік «Застосувати» на
    категорії з десятками характеристик (типово для електроніки) ганяє по
    важкому SQL-запиту на КОЖНУ групу (N+1), навіть коли вибрано лише 1-2.
    """
    from apps.catalog.models import Product
    from apps.catalog.services import get_disjunctive_facets

    # 10 непов'язаних фасетних груп ("шум") + 1 обрана група — імітує
    # категорію на кшталт "Комплектуючі до ПК" з десятками характеристик.
    selected_group = filter_group_factory(name="Selected")
    f_selected = filter_factory(name="Значення A", group=selected_group)
    product = product_factory(slug="perf-facets-product")
    product_filter_factory(product, f_selected)

    for i in range(10):
        noise_group = filter_group_factory(name=f"Noise {i}")
        f_noise = filter_factory(name="Опція", group=noise_group)
        product_filter_factory(product, f_noise)

    # Незалежно від 11 фасетних груп — 1 обрана (leave-one-out) + 1 спільний
    # запит на всі невибрані, плюс кілька службових (base qs, discover groups) —
    # НЕ ~11+ важких запитів, як було до оптимізації.
    with django_assert_max_num_queries(10):
        facets = get_disjunctive_facets(
            Product.objects.all(),
            filter_ids=[f_selected.id],
        )

    assert selected_group.pk in facets
    assert len(facets) == 11
