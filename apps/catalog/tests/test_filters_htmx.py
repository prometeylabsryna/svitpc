"""Integration: category filters via full page + HTMX (grid + OOB forms)."""

from __future__ import annotations

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestCategoryFiltersHtmx:
    def _setup(
        self,
        category_factory,
        product_factory,
        filter_group_factory,
        filter_factory,
        product_filter_factory,
    ):
        cat = category_factory(name="Filters Cat", slug="filters-htmx-cat", is_active=True, is_top=True)
        group = filter_group_factory(name="Колір-htmx")
        f_red = filter_factory(name="Червоний", group=group)
        f_blue = filter_factory(name="Синій", group=group)

        p_red = product_factory(slug="htmx-red", name="Red Item", has_display_image=True)
        p_blue = product_factory(slug="htmx-blue", name="Blue Item", has_display_image=True)
        p_red.categories.add(cat)
        p_blue.categories.add(cat)
        product_filter_factory(p_red, f_red)
        product_filter_factory(p_blue, f_blue)
        return cat, f_red, f_blue, p_red, p_blue

    def test_full_page_shows_both_products_and_facet_counts(
        self, client, category_factory, product_factory, filter_group_factory,
        filter_factory, product_filter_factory,
    ):
        cat, f_red, f_blue, p_red, p_blue = self._setup(
            category_factory, product_factory, filter_group_factory,
            filter_factory, product_filter_factory,
        )
        url = reverse("catalog:category", kwargs={"slug": cat.slug})
        response = client.get(url)
        assert response.status_code == 200
        body = response.content.decode()
        assert p_red.name in body
        assert p_blue.name in body
        assert 'id="desktop-filters-form"' in body
        assert 'id="mobile-filters-form"' in body
        assert 'hx-push-url="true"' in body
        assert 'hx-trigger="submit"' in body
        assert "change delay:300ms" not in body
        assert 'data-filters-apply' in body
        assert "Застосувати" in body
        assert f'value="{f_red.id}"' in body
        assert f'value="{f_blue.id}"' in body

    def test_filter_query_narrows_products(
        self, client, category_factory, product_factory, filter_group_factory,
        filter_factory, product_filter_factory,
    ):
        cat, f_red, f_blue, p_red, p_blue = self._setup(
            category_factory, product_factory, filter_group_factory,
            filter_factory, product_filter_factory,
        )
        url = reverse("catalog:category", kwargs={"slug": cat.slug})
        response = client.get(url, {"f": f_red.id})
        assert response.status_code == 200
        body = response.content.decode()
        assert p_red.name in body
        assert p_blue.name not in body
        # Disjunctive: sibling option still listed
        assert f'value="{f_blue.id}"' in body
        assert f'value="{f_red.id}"' in body
        assert 'checked' in body

    def test_htmx_returns_grid_and_oob_filter_forms(
        self, client, category_factory, product_factory, filter_group_factory,
        filter_factory, product_filter_factory,
    ):
        cat, f_red, f_blue, p_red, p_blue = self._setup(
            category_factory, product_factory, filter_group_factory,
            filter_factory, product_filter_factory,
        )
        url = reverse("catalog:category", kwargs={"slug": cat.slug})
        response = client.get(
            url,
            {"f": f_red.id},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        body = response.content.decode()
        assert 'id="product-grid"' in body
        assert p_red.name in body
        assert p_blue.name not in body
        # Both panels updated out-of-band
        assert 'id="desktop-filters-form"' in body
        assert 'id="mobile-filters-form"' in body
        assert 'hx-swap-oob="true"' in body
        assert body.count('hx-swap-oob="true"') == 2
        # Facet counts refreshed in OOB forms (sibling still present)
        assert f'value="{f_blue.id}"' in body

    def test_bad_price_param_does_not_500(
        self, client, category_factory, product_factory,
    ):
        cat = category_factory(name="Price Cat", slug="filters-price-cat", is_active=True)
        p = product_factory(slug="price-ok", has_display_image=True)
        p.categories.add(cat)
        url = reverse("catalog:category", kwargs={"slug": cat.slug})
        response = client.get(url, {"price_min": "100,5", "price_max": "abc"})
        assert response.status_code == 200

    def test_in_stock_zero_does_not_force_stock_filter(
        self, client, category_factory, product_factory,
    ):
        cat = category_factory(name="Stock Cat", slug="filters-stock-cat", is_active=True)
        p = product_factory(
            slug="oos-shown",
            stock=0,
            hide_if_out_of_stock=False,
            is_visible=True,
            has_display_image=True,
        )
        p.categories.add(cat)
        url = reverse("catalog:category", kwargs={"slug": cat.slug})
        response = client.get(url, {"in_stock": "0"})
        assert response.status_code == 200
        assert "oos-shown" in response.content.decode() or p.name in response.content.decode()
