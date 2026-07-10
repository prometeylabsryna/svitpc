import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_product_detail_hidden_out_of_stock(client, product_factory):
    product = product_factory(
        slug="seagate-st500lm000-test",
        stock=0,
        hide_if_out_of_stock=True,
        is_visible=False,
    )
    response = client.get(reverse("catalog:product", kwargs={"slug": product.slug}))
    assert response.status_code == 200
    assert "Немає в наявності" in response.content.decode()


@pytest.mark.django_db
def test_category_view_hides_empty_subcategories(client, category_factory, product_factory):
    """Subcategory tiles without any product must not render on the category page."""
    parent = category_factory(name="Ноутбуки, планшети", slug="view-laptops-tablets", is_active=True)
    filled_child = category_factory(name="Ноутбуки", slug="view-laptops", parent=parent, is_active=True)
    empty_child = category_factory(name="Планшети", slug="view-tablets", parent=parent, is_active=True)

    product = product_factory(slug="view-laptop-product")
    product.categories.add(filled_child)

    response = client.get(reverse("catalog:category", kwargs={"slug": parent.slug}))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Ноутбуки" in content
    assert empty_child.get_absolute_url() not in content


@pytest.mark.django_db
def test_category_view_404_for_empty_category(client, category_factory):
    """Top-level category without visible products must return 404."""
    empty = category_factory(name="Гаджети", slug="view-gadgets-empty", is_active=True, is_top=True)

    response = client.get(reverse("catalog:category", kwargs={"slug": empty.slug}))

    assert response.status_code == 404
