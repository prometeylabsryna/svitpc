"""Tests for Google Merchant / Ads XML feeds."""

from decimal import Decimal

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_merchant_feed_sale_price(client, product_factory, category_factory):
    # Основний Merchant-фід охоплює лише категорії з ANALYTICS_FEED_CATEGORY_SLUGS
    # (див. test_feeds_categories.py) — тут беремо один зі slug-ів за замовчуванням.
    category = category_factory(name="Ноутбуки, планшети", slug="ноутбуки-планшети")
    product = product_factory(
        name="Sale item",
        slug="sale-item",
        price=Decimal("800.00"),
        old_price=Decimal("1000.00"),
        stock=5,
    )
    product.categories.add(category)
    response = client.get(reverse("google_merchant"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "<g:sale_price>" in body and "800" in body and "UAH</g:sale_price>" in body
    assert "<g:price>" in body and "1000" in body
    assert "google_product_category" not in body
    assert "<g:product_type>" in body


@pytest.mark.django_db
def test_remarketing_feed_rss_format(client, product_factory):
    product_factory(name="Feed item", slug="feed-item", stock=1)
    response = client.get(reverse("google_ads"))
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/xml")
    body = response.content.decode()
    assert 'xmlns:g="http://base.google.com/ns/1.0"' in body
    assert "<g:id>" in body
    assert "<g:image_link>" not in body or "<g:title>" in body
