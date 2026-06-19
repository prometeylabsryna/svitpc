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
