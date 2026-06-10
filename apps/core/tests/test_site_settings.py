import pytest
from django.core.cache import cache

from apps.core.models import SITE_SETTINGS_CACHE_KEY, SiteSettings


@pytest.fixture(autouse=True)
def reset_site_settings(db):
    cache.delete(SITE_SETTINGS_CACHE_KEY)
    SiteSettings.objects.all().delete()
    yield
    cache.delete(SITE_SETTINGS_CACHE_KEY)


@pytest.mark.django_db
def test_site_settings_singleton():
    first = SiteSettings.load()
    first.phone = "+380501112233"
    first.save()
    second = SiteSettings.load()
    assert second.pk == 1
    assert second.phone == "+380501112233"
    assert SiteSettings.objects.count() == 1


@pytest.mark.django_db
def test_site_settings_cache_invalidated_on_save():
    SiteSettings.load()
    cache.set(SITE_SETTINGS_CACHE_KEY, "stale", timeout=None)
    site = SiteSettings.objects.get(pk=1)
    site.email = "shop@example.com"
    site.save()
    assert cache.get(SITE_SETTINGS_CACHE_KEY) is None
    assert SiteSettings.load().email == "shop@example.com"


@pytest.mark.django_db
def test_site_settings_localized_name():
    site = SiteSettings.load()
    site.name = "СвітПК"
    site.name_en = "SvitPC"
    site.save()
    assert site.localized("name", lang="uk") == "СвітПК"
    assert site.localized("name", lang="en") == "SvitPC"
    site.name_en = ""
    site.save()
    assert site.localized("name", lang="en") == "СвітПК"


@pytest.mark.django_db
def test_effective_viber_phone_fallback():
    site = SiteSettings.load()
    site.phone = "+380501112233"
    site.viber_phone = ""
    site.save()
    assert site.effective_viber_phone() == "+380501112233"

    site.viber_phone = "096-076-30-15"
    site.save()
    assert site.effective_viber_phone() == "096-076-30-15"


@pytest.mark.django_db
def test_site_context_includes_viber_phone(client):
    site = SiteSettings.load()
    site.phone = "+380501112233"
    site.viber_phone = "096-076-30-15"
    site.save()
    response = client.get("/returns/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "096-076-30-15" in content
    assert "viber://chat?number=%2B380960763015" in content


@pytest.mark.django_db
def test_site_context_processor(client):
    site = SiteSettings.load()
    site.phone = "+380991234567"
    site.email = "contact@svitpc.ua"
    site.save()
    response = client.get("/")
    assert response.status_code == 200
    assert "+380991234567" in response.content.decode()
    assert "contact@svitpc.ua" in response.content.decode()
