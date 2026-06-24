import pytest
from decimal import Decimal


@pytest.mark.django_db
class TestGetFilteredProducts:
    def test_filters_visible_only(self, product_factory):
        from apps.catalog.models import Product
        from apps.catalog.services import get_filtered_products

        product_factory(is_visible=True, stock=5)
        product_factory(is_visible=False, stock=0)
        qs = get_filtered_products(Product.objects.all())
        assert all(p.is_visible for p in qs)

    def test_price_min_filter(self, product_factory):
        from apps.catalog.models import Product
        from apps.catalog.services import get_filtered_products

        product_factory(price=Decimal("100"), is_visible=True, stock=1, slug="cheap")
        product_factory(price=Decimal("500"), is_visible=True, stock=1, slug="expensive")
        qs = get_filtered_products(Product.objects.all(), price_min=Decimal("200"))
        assert all(p.price >= 200 for p in qs)

    def test_price_max_filter(self, product_factory):
        from apps.catalog.models import Product
        from apps.catalog.services import get_filtered_products

        product_factory(price=Decimal("100"), is_visible=True, stock=1, slug="cheap2")
        product_factory(price=Decimal("500"), is_visible=True, stock=1, slug="expensive2")
        qs = get_filtered_products(Product.objects.all(), price_max=Decimal("200"))
        assert all(p.price <= 200 for p in qs)

    def test_in_stock_filter(self, product_factory):
        from apps.catalog.models import Product
        from apps.catalog.services import get_filtered_products

        product_factory(stock=0, is_visible=True, slug="no-stock")
        product_factory(stock=5, is_visible=True, slug="has-stock")
        qs = get_filtered_products(Product.objects.all(), in_stock_only=True)
        assert all(p.stock > 0 for p in qs)

    def test_visible_catalog_hides_zero_stock_when_flag_set(self, product_factory):
        from apps.catalog.services import visible_catalog_products

        product_factory(
            slug="hidden-oos",
            is_visible=True,
            stock=0,
            hide_if_out_of_stock=True,
        )
        product_factory(
            slug="shown-oos-allowed",
            is_visible=True,
            stock=0,
            hide_if_out_of_stock=False,
        )
        product_factory(slug="in-stock", is_visible=True, stock=3, hide_if_out_of_stock=True)

        slugs = set(visible_catalog_products().values_list("slug", flat=True))
        assert "hidden-oos" not in slugs
        assert "shown-oos-allowed" in slugs
        assert "in-stock" in slugs

    def test_filters_or_within_group(
        self, product_factory, filter_group_factory, filter_factory, product_filter_factory
    ):
        """Selecting multiple values from the same group returns products matching ANY of them."""
        from apps.catalog.models import Product
        from apps.catalog.services import get_filtered_products

        group = filter_group_factory(name="Capacity")
        f700 = filter_factory(name="700 мл", group=group)
        f800 = filter_factory(name="800 мл", group=group)
        f500 = filter_factory(name="500 мл", group=group)

        p700 = product_factory(slug="p700")
        p800 = product_factory(slug="p800")
        p500 = product_factory(slug="p500")
        product_filter_factory(p700, f700)
        product_filter_factory(p800, f800)
        product_filter_factory(p500, f500)

        qs = get_filtered_products(Product.objects.all(), filters=[f700.id, f800.id])
        slugs = {p.slug for p in qs}
        assert "p700" in slugs
        assert "p800" in slugs
        assert "p500" not in slugs

    def test_filters_and_between_groups(
        self, product_factory, filter_group_factory, filter_factory, product_filter_factory
    ):
        """Values from different groups are ANDed: product must match at least one value from each group."""
        from apps.catalog.models import Product
        from apps.catalog.services import get_filtered_products

        g_capacity = filter_group_factory(name="Capacity2")
        g_color = filter_group_factory(name="Color")
        f700 = filter_factory(name="700 мл", group=g_capacity)
        f_red = filter_factory(name="Червоний", group=g_color)
        f_blue = filter_factory(name="Синій", group=g_color)

        p_700_red = product_factory(slug="p-700-red")
        p_700_blue = product_factory(slug="p-700-blue")
        p_700_only = product_factory(slug="p-700-only")

        product_filter_factory(p_700_red, f700)
        product_filter_factory(p_700_red, f_red)
        product_filter_factory(p_700_blue, f700)
        product_filter_factory(p_700_blue, f_blue)
        product_filter_factory(p_700_only, f700)

        # capacity=700 AND (color=red OR color=blue)
        qs = get_filtered_products(
            Product.objects.all(), filters=[f700.id, f_red.id, f_blue.id]
        )
        slugs = {p.slug for p in qs}
        assert "p-700-red" in slugs
        assert "p-700-blue" in slugs
        assert "p-700-only" not in slugs


@pytest.mark.django_db
class TestCategoryListingProducts:
    def test_includes_products_on_ancestor_category(self, category_factory, product_factory):
        from apps.catalog.services import category_listing_products

        parent = category_factory(name="Parent", slug="parent-cat")
        child = category_factory(name="Child", slug="child-cat", parent=parent)
        sibling = category_factory(name="Sibling", slug="sibling-cat", parent=parent)

        on_parent = product_factory(
            slug="on-parent",
            image_url="https://cdn.example.com/p.jpg",
        )
        on_parent.categories.set([parent])

        on_sibling = product_factory(
            slug="on-sibling",
            image_url="https://cdn.example.com/s.jpg",
        )
        on_sibling.categories.set([sibling])

        slugs = set(category_listing_products(child).values_list("slug", flat=True))
        assert "on-parent" in slugs
        assert "on-sibling" not in slugs

