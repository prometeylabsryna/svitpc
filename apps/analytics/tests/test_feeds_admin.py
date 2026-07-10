"""Tests for feed stats and admin dashboard."""

from decimal import Decimal

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_collect_feed_stats_counts(product_factory, category_factory, settings):
    settings.SITE_URL = "https://svitpc.com.ua"
    # Merchant-фід охоплює лише ANALYTICS_FEED_CATEGORY_SLUGS — товар без такої
    # категорії лишається "видимим", але не "eligible" для основного фіда.
    category = category_factory(name="Ноутбуки, планшети", slug="ноутбуки-планшети")
    in_stock = product_factory(name="In stock", slug="in-stock", stock=3)
    in_stock.categories.add(category)
    product_factory(name="Out of stock", slug="out-stock", stock=0)
    from apps.analytics.feeds import collect_feed_stats

    stats = collect_feed_stats()
    assert stats.visible_products == 2
    assert stats.merchant_eligible == 1
    assert stats.merchant_in_feed == 1
    assert stats.site_url == "https://svitpc.com.ua"


@pytest.mark.django_db
def test_absolute_feed_url_uses_site_url(settings):
    settings.SITE_URL = "https://svitpc.com.ua"
    from apps.analytics.feeds import absolute_feed_url

    url = absolute_feed_url(None, "google-merchant")
    assert url == "https://svitpc.com.ua/feeds/google-merchant.xml"


@pytest.mark.django_db
def test_feeds_admin_requires_login(client):
    response = client.get(reverse("admin:analytics_feeds_dashboard"))
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_feeds_admin_dashboard(client, product_factory, settings):
    from django.contrib.auth import get_user_model

    settings.SITE_URL = "https://svitpc.com.ua"
    User = get_user_model()
    user = User.objects.create_superuser(email="a@test.com", password="pass")
    product_factory(
        name="Merchant item",
        slug="merchant-item",
        stock=2,
        price=Decimal("100.00"),
        short_description="Short",
    )
    client.force_login(user)
    # SplitSessionMiddleware: адмінка читає окремий cookie admin_sessionid
    from django.conf import settings as dj_settings

    client.cookies[dj_settings.ADMIN_SESSION_COOKIE_NAME] = client.cookies[
        dj_settings.SESSION_COOKIE_NAME
    ].value
    response = client.get(reverse("admin:analytics_feeds_dashboard"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Google Merchant Center" in body
    assert "https://svitpc.com.ua/feeds/google-merchant.xml" in body
    assert "https://svitpc.com.ua/feeds/google-ads.xml" in body
