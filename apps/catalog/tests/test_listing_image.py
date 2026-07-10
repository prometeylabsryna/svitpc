import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.catalog.listing_image import (
    _resize_to_webp,
    ensure_listing_webp,
    is_allowed_remote_url,
    listing_source_key,
)


class TestAllowedRemoteUrl:
    @pytest.mark.parametrize(
        "url,ok",
        [
            ("https://opt.brain.com.ua/static/images/prod_img/1/3/U1.jpg", True),
            (
                "https://kancmaster.com.ua/image/cache/catalog/import_files/x.jpg",
                True,
            ),
            ("https://evil.example/photo.jpg", False),
            ("", False),
        ],
    )
    def test_host_allowlist(self, url, ok):
        assert is_allowed_remote_url(url) is ok


class TestResizeToWebp:
    def test_outputs_webp_bytes(self):
        from PIL import Image
        import io

        img = Image.new("RGB", (640, 480), color=(120, 80, 40))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        out = _resize_to_webp(buf.getvalue(), size=300)
        assert out[:4] == b"RIFF"
        assert len(out) < len(buf.getvalue())


@pytest.mark.django_db
class TestListingSourceKey:
    def test_external_url_key_stable(self, product_factory):
        product = product_factory(image_url="https://opt.brain.com.ua/static/images/prod_img/1/1/U1.jpg")
        assert listing_source_key(product) == listing_source_key(product)

    def test_listing_image_url_uses_proxy_for_brain(self, product_factory):
        product = product_factory(image_url="https://opt.brain.com.ua/static/images/prod_img/1/1/U1.jpg")
        assert product.listing_image_url == reverse("product_listing_image", kwargs={"pk": product.pk})

    def test_listing_image_url_uses_proxy_for_kancmaster(self, product_factory):
        product = product_factory(
            image_url="https://kancmaster.com.ua/image/cache/catalog/x.jpg",
        )
        assert product.listing_image_url == reverse("product_listing_image", kwargs={"pk": product.pk})

    def test_listing_image_url_direct_for_unknown_host(self, product_factory):
        product = product_factory(image_url="https://cdn.example.com/photo.jpg")
        assert product.listing_image_url == "https://cdn.example.com/photo.jpg"


@pytest.mark.django_db
def test_listing_image_view_redirects_when_no_photo(client, product_factory):
    product = product_factory(image_url="", image="")
    response = client.get(reverse("product_listing_image", kwargs={"pk": product.pk}))
    assert response.status_code in (302, 301)


@pytest.mark.django_db
class TestListingImageFetchFailureFallback:
    """Постачальник (Kancmaster) інколи блокує IP серверу (403), лишаючись
    доступним для браузера клієнта — тож при збої серверного фетчу картка
    має вести напряму на зовнішній URL, а не на заглушку no-photo."""

    def test_view_redirects_to_source_url_on_fetch_failure(self, client, product_factory, monkeypatch):
        cache.clear()
        url = "https://kancmaster.com.ua/image/catalog/broken.jpg"
        product = product_factory(image_url=url, image="")

        monkeypatch.setattr("apps.catalog.listing_image.fetch_listing_webp", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("403")))

        response = client.get(reverse("product_listing_image", kwargs={"pk": product.pk}))
        assert response.status_code in (302, 301)
        assert response["Location"] == url

    def test_repeated_failure_short_circuits_without_refetching(self, product_factory, monkeypatch):
        cache.clear()
        url = "https://kancmaster.com.ua/image/catalog/broken2.jpg"
        product = product_factory(image_url=url, image="")

        calls = {"n": 0}

        def _boom(*_a, **_k):
            calls["n"] += 1
            raise RuntimeError("403")

        monkeypatch.setattr("apps.catalog.listing_image.fetch_listing_webp", _boom)

        assert ensure_listing_webp(product) is None
        assert ensure_listing_webp(product) is None
        assert calls["n"] == 1
