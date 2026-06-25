"""Integration/unit tests for Kancmaster sync_all task."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

FEED_ITEMS = [
    {
        "id": "1",
        "name": "Ручка",
        "price": "20.00",
        "quantity": "10",
        "category": "Ручки",
        "brand": "Pilot",
        "sku": "P-001",
        "description": "Опис",
        "params": [
            {"name": "Колір", "value": "синій"},
            {"name": "Товщина", "value": "0.7 мм"},
        ],
        "image_url": "https://cdn.example.com/pen.jpg",
        "image_urls": ["https://cdn.example.com/pen.jpg", "https://cdn.example.com/pen2.jpg"],
    },
    {
        "id": "2",
        "name": "Олівець",
        "price": "5.00",
        "quantity": "0",
        "category": "Олівці",
        "brand": "",
        "sku": "",
        "description": "",
        "params": [],
        "image_url": "",
        "image_urls": [],
    },
]


@pytest.mark.django_db
class TestSyncAll:
    def _patch_client(self, items=None):
        mock_client = MagicMock()
        mock_client.fetch_xml.return_value = b"<xml/>"
        mock_client.parse_products.return_value = items if items is not None else FEED_ITEMS
        return patch(
            "apps.integrations.kancmaster.tasks.KancmasterXMLClient",
            return_value=mock_client,
        )

    def test_creates_new_products(self):
        from apps.catalog.models import Product
        from apps.integrations.kancmaster.tasks import sync_all

        with self._patch_client():
            sync_all()

        assert Product.objects.filter(source=Product.SOURCE_KANCMASTER).count() == 2

    def test_product_fields_set_correctly(self):
        from apps.catalog.models import Product
        from apps.integrations.kancmaster.tasks import sync_all

        with self._patch_client():
            sync_all()

        pen = Product.objects.get(source=Product.SOURCE_KANCMASTER, external_id="1")
        assert pen.name == "Ручка"
        assert pen.sku == "P-001"
        assert pen.stock == 10
        assert pen.is_visible is True
        assert pen.image_url == "https://cdn.example.com/pen.jpg"

    def test_out_of_stock_not_visible(self):
        from apps.catalog.models import Product
        from apps.integrations.kancmaster.tasks import sync_all

        with self._patch_client():
            sync_all()

        pencil = Product.objects.get(source=Product.SOURCE_KANCMASTER, external_id="2")
        assert pencil.stock == 0
        assert pencil.is_visible is False

    def test_category_created_and_mapped(self):
        from apps.catalog.models import Category, Product
        from apps.integrations.kancmaster.tasks import sync_all

        with self._patch_client():
            sync_all()

        assert Category.objects.filter(kancmaster_name="Ручки").exists()
        pen = Product.objects.get(source=Product.SOURCE_KANCMASTER, external_id="1")
        assert pen.categories.filter(kancmaster_name="Ручки").exists()

    def test_brand_created(self):
        from apps.catalog.models import Brand
        from apps.integrations.kancmaster.tasks import sync_all

        with self._patch_client():
            sync_all()

        assert Brand.objects.filter(name="Pilot").exists()

    def test_brand_slug_collision_does_not_fail_sync(self):
        from apps.catalog.models import Brand, Product
        from apps.integrations.kancmaster.tasks import sync_all

        Brand.objects.create(name="KOH-I-NOOR", slug="koh-i-noor")
        feed = [{**FEED_ITEMS[0], "id": "301", "brand": "Koh-I-Noor"}]
        with self._patch_client(items=feed):
            sync_all()

        assert Product.objects.filter(source=Product.SOURCE_KANCMASTER, external_id="301").exists()

    def test_gallery_images_synced(self):
        from apps.integrations.kancmaster.tasks import sync_all
        from apps.catalog.models import Product

        with self._patch_client():
            sync_all()

        pen = Product.objects.get(source=Product.SOURCE_KANCMASTER, external_id="1")
        gallery_urls = list(pen.images.values_list("image_url", flat=True))
        assert "https://cdn.example.com/pen2.jpg" in gallery_urls

    def test_product_attributes_synced(self):
        from apps.catalog.models import Product, ProductAttribute
        from apps.integrations.kancmaster.tasks import sync_all

        with self._patch_client():
            sync_all()

        pen = Product.objects.get(source=Product.SOURCE_KANCMASTER, external_id="1")
        attrs = dict(
            ProductAttribute.objects.filter(product=pen).values_list(
                "attribute__name", "value"
            )
        )
        assert attrs["Колір"] == "синій"
        assert attrs["Товщина"] == "0.7 мм"

    def test_updates_existing_product(self):
        from apps.catalog.models import Product
        from apps.integrations.kancmaster.tasks import sync_all

        with self._patch_client():
            sync_all()  # create

        updated_feed = [{**FEED_ITEMS[0], "price": "30.00", "quantity": "5", "description": "Новий опис"}]
        with self._patch_client(items=updated_feed):
            sync_all()  # update

        pen = Product.objects.get(source=Product.SOURCE_KANCMASTER, external_id="1")
        assert pen.purchase_price == Decimal("30.00")
        assert pen.stock == 5
        assert pen.description == "Новий опис"
        assert pen.is_visible is True
        assert Product.objects.filter(source=Product.SOURCE_KANCMASTER, external_id="1").count() == 1

    def test_deactivates_removed_products(self):
        from apps.catalog.models import Product
        from apps.integrations.kancmaster.tasks import sync_all

        with self._patch_client():
            sync_all()  # creates id=1 and id=2

        # Feed now only has id=1
        with self._patch_client(items=[FEED_ITEMS[0]]):
            sync_all()

        pencil = Product.objects.get(source=Product.SOURCE_KANCMASTER, external_id="2")
        assert pencil.is_visible is False
        assert pencil.stock == 0

    def test_empty_xml_response_skips_sync(self):
        from apps.catalog.models import Product
        from apps.integrations.kancmaster.tasks import sync_all

        mock_client = MagicMock()
        mock_client.fetch_xml.return_value = None
        with patch("apps.integrations.kancmaster.tasks.KancmasterXMLClient", return_value=mock_client):
            sync_all()

        assert Product.objects.filter(source=Product.SOURCE_KANCMASTER).count() == 0

    def test_bad_price_does_not_crash_sync(self):
        from apps.catalog.models import Product
        from apps.integrations.kancmaster.tasks import sync_all

        bad_item = {**FEED_ITEMS[0], "id": "99", "price": "N/A"}
        with self._patch_client(items=[bad_item, FEED_ITEMS[1]]):
            sync_all()

        # The bad item should still create (price defaults to 0), and pencil also created
        assert Product.objects.filter(source=Product.SOURCE_KANCMASTER).count() == 2

    def test_idempotent_on_double_run(self):
        from apps.catalog.models import Product
        from apps.integrations.kancmaster.tasks import sync_all

        with self._patch_client():
            sync_all()
            sync_all()

        assert Product.objects.filter(source=Product.SOURCE_KANCMASTER).count() == 2

    def test_gallery_resync_without_sort_order_conflict(self):
        from apps.catalog.models import Product, ProductImage
        from apps.integrations.kancmaster.tasks import _external_gallery_qs, sync_all

        with self._patch_client():
            sync_all()

        pen = Product.objects.get(source=Product.SOURCE_KANCMASTER, external_id="1")
        ProductImage.objects.filter(product=pen, image="").update(sort_order=99)

        with self._patch_client():
            sync_all()

        orders = list(
            _external_gallery_qs(pen).order_by("sort_order").values_list("sort_order", flat=True)
        )
        assert orders == [1]

    def test_category_replaced_on_update(self):
        from apps.catalog.models import Category, Product
        from apps.integrations.kancmaster.tasks import sync_all

        with self._patch_client():
            sync_all()

        pen = Product.objects.get(source=Product.SOURCE_KANCMASTER, external_id="1")
        assert pen.categories.filter(kancmaster_name="Ручки").exists()

        moved_feed = [{**FEED_ITEMS[0], "category": "Олівці"}]
        with self._patch_client(items=moved_feed):
            sync_all()

        pen.refresh_from_db()
        assert pen.categories.filter(kancmaster_name="Олівці").exists()
        assert not pen.categories.filter(kancmaster_name="Ручки").exists()
        assert Category.objects.filter(kancmaster_name="Олівці").exists()
