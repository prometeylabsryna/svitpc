"""Pytest fixtures (factories) for SvitPC tests."""

import itertools

import pytest

_counter = itertools.count(1)



@pytest.fixture
def brand_factory(db):
    from apps.catalog.models import Brand

    def make(name="Test Brand", **kwargs):
        n = next(_counter)
        kwargs.setdefault("slug", f"brand-{n}")
        return Brand.objects.create(name=name, **kwargs)

    return make


@pytest.fixture
def category_factory(db):
    from apps.catalog.models import Category

    def make(name="Test Category", **kwargs):
        n = next(_counter)
        slug = kwargs.pop("slug", f"category-{n}")
        return Category.objects.create(name=name, slug=slug, **kwargs)

    return make


@pytest.fixture
def product_factory(db):
    from decimal import Decimal

    from apps.catalog.models import Product

    def make(name="Test Product", **kwargs):
        n = next(_counter)
        kwargs.setdefault("price", Decimal("999"))
        kwargs.setdefault("stock", 10)
        kwargs.setdefault("is_visible", True)
        slug = kwargs.pop("slug", f"test-product-{n}")
        return Product.objects.create(name=name, slug=slug, **kwargs)

    return make


@pytest.fixture
def filter_group_factory(db):
    from apps.catalog.models import FilterGroup

    def make(name="Test Group", **kwargs):
        n = next(_counter)
        kwargs.setdefault("sort_order", 0)
        return FilterGroup.objects.create(name=name or f"Group {n}", **kwargs)

    return make


@pytest.fixture
def filter_factory(db, filter_group_factory):
    from apps.catalog.models import Filter

    def make(name="Test Filter", group=None, **kwargs):
        n = next(_counter)
        if group is None:
            group = filter_group_factory(name=f"AutoGroup {n}")
        return Filter.objects.create(name=name, group=group, **kwargs)

    return make


@pytest.fixture
def product_filter_factory(db):
    from apps.catalog.models import ProductFilter

    def make(product, filter_obj):
        return ProductFilter.objects.create(product=product, filter=filter_obj)

    return make


@pytest.fixture
def customer_factory(db):
    from apps.customers.models import Customer

    def make(email=None, **kwargs):
        n = next(_counter)
        email = email or f"test{n}@example.com"
        kwargs.setdefault("password", "testpass123")
        return Customer.objects.create_user(email=email, **kwargs)

    return make
