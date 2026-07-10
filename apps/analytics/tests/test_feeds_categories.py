"""Основний Google Merchant фід звужено до категорій ноутбуків/комп'ютерів/
комплектуючих (+ підкатегорії) і обмежено ANALYTICS_FEED_MAX_PRODUCTS товарами."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestMerchantFeedCategoryFilter:
    def test_product_outside_target_categories_excluded(self, client, product_factory, category_factory):
        other = category_factory(name="Канцтовари", slug="kantstovary")
        product = product_factory(name="Ручка", slug="ruchka", stock=5)
        product.categories.add(other)

        response = client.get(reverse("google_merchant"))
        body = response.content.decode()
        assert "Ручка" not in body

    def test_product_in_target_root_category_included(self, client, product_factory, category_factory):
        category = category_factory(name="Ноутбуки, планшети", slug="ноутбуки-планшети")
        product = product_factory(name="Леново", slug="lenovo-x1", stock=5)
        product.categories.add(category)

        response = client.get(reverse("google_merchant"))
        body = response.content.decode()
        assert "Леново" in body

    def test_product_in_target_subcategory_included(self, client, product_factory, category_factory):
        root = category_factory(name="Комп'ютери, аксесуари", slug="компютери-аксесуари")
        child = category_factory(name="Монітори", slug="monitory", parent=root)
        product = product_factory(name="Монітор Dell", slug="dell-monitor", stock=5)
        product.categories.add(child)

        response = client.get(reverse("google_merchant"))
        body = response.content.decode()
        assert "Монітор Dell" in body

    def test_out_of_stock_still_excluded_even_in_target_category(self, client, product_factory, category_factory):
        category = category_factory(name="Комплектуючі до ПК", slug="комплектуючі-до-пк")
        product = product_factory(name="SSD Kingston", slug="ssd-kingston", stock=0)
        product.categories.add(category)

        response = client.get(reverse("google_merchant"))
        body = response.content.decode()
        assert "SSD Kingston" not in body


@pytest.mark.django_db
def test_merchant_feed_capped_at_max_products(client, product_factory, category_factory, settings):
    settings.ANALYTICS_FEED_MAX_PRODUCTS = 2
    category = category_factory(name="Ноутбуки, планшети", slug="ноутбуки-планшети")
    for i in range(4):
        p = product_factory(name=f"Товар {i}", slug=f"tovar-{i}", stock=1)
        p.categories.add(category)

    from apps.analytics.feeds import merchant_feed_queryset

    assert merchant_feed_queryset().count() == 2


@pytest.mark.django_db
def test_feed_category_ids_uses_settings_slugs(category_factory, settings):
    settings.ANALYTICS_FEED_CATEGORY_SLUGS = ["custom-slug"]
    included = category_factory(name="Custom", slug="custom-slug")
    category_factory(name="Not included", slug="other-slug")

    from apps.analytics.feeds import feed_category_ids

    assert feed_category_ids() == [included.pk]
