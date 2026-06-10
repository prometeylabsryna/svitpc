import pytest

from apps.catalog.gallery import (
    cleanup_product_gallery,
    filter_products_missing_display_image,
    filter_products_with_display_image,
    is_placeholder_image_url,
    is_stale_gallery_url,
    is_valid_product_image_url,
    normalize_brain_image_url,
    product_gallery_urls,
    resolve_product_image_url,
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


class TestPlaceholderImageUrl:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://opt.brain.com.ua/static/images/prod_img/2/1/no-photo-api.png", True),
            ("https://opt.brain.com.ua/static/images/prod_img/8/7/U0582287_big.jpg", False),
            ("", False),
        ],
    )
    def test_brain_placeholder_detected(self, url, expected):
        assert is_placeholder_image_url(url) is expected

    def test_normalize_brain_returns_empty_for_placeholder(self):
        assert normalize_brain_image_url(
            "https://opt.brain.com.ua/static/images/prod_img/2/1/no-photo-api.png",
        ) == ""


@pytest.mark.django_db
class TestDisplayImageFilters:
    def test_with_display_image_matches_resolve(self, product_factory):
        with_url = product_factory(image_url="https://cdn.example.com/big.jpg")
        missing = product_factory(image_url="")
        assert filter_products_with_display_image(
            type(with_url).objects.filter(pk=with_url.pk),
        ).exists()
        assert not filter_products_with_display_image(
            type(missing).objects.filter(pk=missing.pk),
        ).exists()
        assert filter_products_missing_display_image(
            type(missing).objects.filter(pk=missing.pk),
        ).exists()

    def test_placeholder_excluded_from_with_display_image(self, product_factory):
        product = product_factory(
            image_url="https://opt.brain.com.ua/static/images/prod_img/2/1/no-photo-api.png",
        )
        assert not filter_products_with_display_image(
            type(product).objects.filter(pk=product.pk),
        ).exists()


@pytest.mark.django_db
class TestResolveProductImageUrl:
    def test_placeholder_main_falls_back_to_gallery(self, product_factory):
        product = product_factory(
            image_url="https://opt.brain.com.ua/static/images/prod_img/2/1/no-photo-api.png",
        )
        ProductImage.objects.create(
            product=product,
            image_url="https://cdn.example.com/real.jpg",
            sort_order=0,
        )
        assert resolve_product_image_url(product) == "https://cdn.example.com/real.jpg"

    def test_placeholder_only_returns_empty(self, product_factory):
        product = product_factory(
            image_url="https://opt.brain.com.ua/static/images/prod_img/2/1/no-photo-api.png",
        )
        assert resolve_product_image_url(product) == ""
        assert product.main_image_url == ""


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

    def test_skips_placeholder_main(self, product_factory):
        product = product_factory(
            image_url="https://opt.brain.com.ua/static/images/prod_img/2/1/no-photo-api.png",
        )
        ProductImage.objects.create(
            product=product,
            image_url="https://cdn.example.com/extra.jpg",
            sort_order=0,
        )
        assert product_gallery_urls(product) == ["https://cdn.example.com/extra.jpg"]
        assert is_valid_product_image_url(product.image_url) is False


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

    def test_clears_brain_placeholder_urls(self, product_factory):
        product = product_factory(
            image_url="https://opt.brain.com.ua/static/images/prod_img/2/1/no-photo-api.png",
        )
        ProductImage.objects.create(
            product=product,
            image_url="https://opt.brain.com.ua/static/images/prod_img/2/1/no-photo-api.png",
            sort_order=0,
        )

        stats = cleanup_product_gallery(dry_run=False)

        product.refresh_from_db()
        assert stats["placeholder_main_cleared"] >= 1
        assert stats["placeholder_gallery_deleted"] >= 1
        assert product.image_url == ""
        assert not product.images.exists()
