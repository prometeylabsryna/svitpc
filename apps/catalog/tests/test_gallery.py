import pytest

from apps.catalog.gallery import (
    cleanup_product_gallery,
    is_stale_gallery_url,
    product_gallery_urls,
)
from apps.catalog.models import ProductImage


class TestStaleGalleryUrl:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://opt.brain.com.ua/static/images/prod_img/8/7/U0582287_2main.jpg", True),
            ("https://opt.brain.com.ua/static/images/prod_img/8/7/U0582287_main.jpg", False),
            ("https://opt.brain.com.ua/static/images/prod_img/8/7/U0582287_big.jpg", False),
            ("", False),
        ],
    )
    def test_numbered_main_detected(self, url, expected):
        assert is_stale_gallery_url(url) is expected


@pytest.mark.django_db
class TestProductGalleryUrls:
    def test_main_only(self, product_factory):
        product = product_factory(
            image_url="https://cdn.example.com/big.jpg",
        )
        assert product_gallery_urls(product) == ["https://cdn.example.com/big.jpg"]

    def test_skips_stale_and_duplicates(self, product_factory):
        product = product_factory(
            image_url="https://cdn.example.com/big.jpg",
        )
        ProductImage.objects.create(
            product=product,
            image_url="https://cdn.example.com/big.jpg",
            sort_order=0,
        )
        ProductImage.objects.create(
            product=product,
            image_url="https://cdn.example.com/extra.jpg",
            sort_order=1,
        )
        ProductImage.objects.create(
            product=product,
            image_url="https://cdn.example.com/U001_3main.jpg",
            sort_order=2,
        )
        assert product_gallery_urls(product) == [
            "https://cdn.example.com/big.jpg",
            "https://cdn.example.com/extra.jpg",
        ]


@pytest.mark.django_db
class TestCleanupProductGallery:
    def test_removes_stale_urls(self, product_factory):
        product = product_factory(image_url="https://cdn.example.com/main.jpg")
        ProductImage.objects.create(
            product=product,
            image_url="https://cdn.example.com/U001_2main.jpg",
            sort_order=0,
        )
        ProductImage.objects.create(
            product=product,
            image_url="https://cdn.example.com/U001_3main.jpg",
            sort_order=1,
        )

        stats = cleanup_product_gallery(dry_run=False)

        assert stats["stale_deleted"] >= 2
        urls = list(product.images.values_list("image_url", flat=True))
        assert "https://cdn.example.com/U001_2main.jpg" not in urls
        assert "https://cdn.example.com/U001_3main.jpg" not in urls

    def test_dedupes_same_url(self, product_factory):
        product = product_factory(image_url="https://cdn.example.com/main.jpg")
        ProductImage.objects.create(
            product=product,
            image_url="https://cdn.example.com/extra.jpg",
            sort_order=0,
        )
        ProductImage.objects.create(
            product=product,
            image_url="https://cdn.example.com/extra.jpg",
            sort_order=1,
        )

        stats = cleanup_product_gallery(dry_run=False)

        assert stats["dup_url_deleted"] >= 1
        urls = list(product.images.values_list("image_url", flat=True))
        assert urls.count("https://cdn.example.com/extra.jpg") == 1
