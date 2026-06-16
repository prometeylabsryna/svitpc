"""Tests for admin category picker."""

import pytest
from django.contrib.admin.sites import site

from apps.catalog.admin import ProductAdmin, ProductAdminForm
from apps.catalog.admin_category_tree import get_admin_category_tree_nodes
from apps.catalog.models import Category
from apps.catalog.widgets import CategoryTreeWidget


@pytest.mark.django_db
def test_category_admin_path_includes_ancestors(category_factory):
    root = category_factory(name="Б/У", slug="bu-path-root")
    child = category_factory(name="Ноутбуки", slug="bu-path-laptops", parent=root)

    assert child.admin_path == "Б/У › Ноутбуки"


@pytest.mark.django_db
def test_product_admin_uses_category_tree_not_filter_horizontal():
    assert "categories" not in getattr(ProductAdmin, "filter_horizontal", ())
    form = ProductAdminForm()
    assert isinstance(form.fields["categories"].widget, CategoryTreeWidget)


@pytest.mark.django_db
def test_product_admin_form_builds_tree_nodes(category_factory):
    root = category_factory(name="Root", slug="tree-root", is_active=True)
    category_factory(name="Child", slug="tree-child", parent=root, is_active=True)
    Category.objects.filter(pk=root.pk).update(level=0, lft=1, rght=4, tree_id=root.tree_id)
    child = Category.objects.get(slug="tree-child")
    Category.objects.filter(pk=child.pk).update(level=1, lft=2, rght=3, tree_id=root.tree_id)

    form = ProductAdminForm()
    paths = [node["path"] for node in form.fields["categories"].widget.nodes]

    assert "Root › Child" in paths


@pytest.mark.django_db
def test_admin_category_tree_nodes_single_query(category_factory, django_assert_num_queries):
    root = category_factory(name="Root", slug="cache-root", is_active=True)
    category_factory(name="Child", slug="cache-child", parent=root, is_active=True)

    get_admin_category_tree_nodes()

    with django_assert_num_queries(0):
        nodes = get_admin_category_tree_nodes()

    assert any("Root › Child" in node["path"] for node in nodes)


@pytest.mark.django_db
def test_category_admin_label_from_instance(category_factory):
    root = category_factory(name="Б/У", slug="bu-label-root")
    child = category_factory(name="Монітори", slug="bu-label-monitors", parent=root)
    admin = site._registry[Category]

    assert admin.label_from_instance(child) == "Б/У › Монітори"
