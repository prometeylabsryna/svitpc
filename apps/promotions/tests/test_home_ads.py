from datetime import timedelta
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.promotions.home_ads import (
    active_home_banners,
    aspect_ratio_for,
    aspect_ratio_label,
    recommended_banner_size,
    slot_width,
)
from apps.promotions.models import Banner, HomeAdSettings


def _banner_image(name: str = "banner.jpg") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, b"fake-image", content_type="image/jpeg")


@pytest.mark.django_db
class TestHomeAdSettings:
    def test_singleton_load(self):
        settings = HomeAdSettings.load()
        assert settings.pk == 1
        assert settings.visible_columns == 4

    def test_recommended_size_scales_with_columns(self):
        w4, h4 = recommended_banner_size(4)
        w2, h2 = recommended_banner_size(2)
        assert w2 > w4
        assert slot_width(2) == w2
        assert aspect_ratio_label(4) == "3:4"
        assert h4 == round(w4 * 4 / 3)
        assert aspect_ratio_label(1) == "20:7"
        w1, h1 = recommended_banner_size(1)
        assert h1 == round(h4 * 1.08)
        assert h1 < round(w1 * 3 / 4)
        assert h2 == round(w2 * 4 / 3)


@pytest.mark.django_db
class TestActiveHomeBanners:
    def test_filters_inactive_and_dates(self):
        now = timezone.now()
        Banner.objects.create(
            title="Active",
            image=_banner_image("active.jpg"),
            position=Banner.POSITION_HOME,
            is_active=True,
        )
        Banner.objects.create(
            title="Inactive",
            image=_banner_image("inactive.jpg"),
            position=Banner.POSITION_HOME,
            is_active=False,
        )
        Banner.objects.create(
            title="Future",
            image=_banner_image("future.jpg"),
            position=Banner.POSITION_HOME,
            is_active=True,
            date_start=now + timedelta(days=1),
        )
        Banner.objects.create(
            title="Category",
            image=_banner_image("cat.jpg"),
            position=Banner.POSITION_CATEGORY,
            is_active=True,
        )

        titles = list(active_home_banners().values_list("title", flat=True))
        assert titles == ["Active"]


@pytest.mark.django_db
class TestHomeView:
    def test_home_shows_ads_section(self, client):
        settings = HomeAdSettings.load()
        settings.visible_columns = 2
        settings.save()

        Banner.objects.create(
            title="Promo 1",
            image=_banner_image("promo.jpg"),
            link="https://example.com",
            position=Banner.POSITION_HOME,
            is_active=True,
        )

        response = client.get("/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "home-ads" in content
        assert "Promo 1" in content
        assert "home-ads--cols-2" in content

    def test_home_without_banners_omits_section(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "home-ads" not in response.content.decode()
