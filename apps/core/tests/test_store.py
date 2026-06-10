import pytest
from django.test import Client
from django.urls import reverse

from apps.core.models import SiteSettings
from apps.core.store import (
    DEFAULT_STORE_ADDRESS,
    STORE_MAPS_QUERY,
    store_address,
    store_maps_embed_url,
    store_maps_url,
)


@pytest.mark.django_db
def test_store_maps_url_uses_business_query():
    url = store_maps_url()
    assert "google.com/maps/search/" in url
    assert "СВІТ" in url or "%D0%A1%D0%92%D0%86%D0%A2" in url
    assert STORE_MAPS_QUERY.split(",")[0].strip() in STORE_MAPS_QUERY


@pytest.mark.django_db
def test_store_maps_embed_url_uses_business_query():
    url = store_maps_embed_url()
    assert "output=embed" in url
    assert "Незалежності" in url or "%D0%9D%D0%B5%D0%B7%D0%B0%D0%BB%D0%B5%D0%B6%D0%BD%D0%BE%D1%81%D1%82%D1%96" in url


@pytest.mark.django_db
def test_store_address_default_when_empty():
    site = SiteSettings.load()
    site.address = ""
    site.save()
    assert "Незалежності" in store_address(site)
    assert str(DEFAULT_STORE_ADDRESS) in store_address(site)


@pytest.mark.django_db
def test_store_address_admin_override():
    site = SiteSettings.load()
    site.address = "вул. Тестова, 1"
    site.save()
    assert store_address(site) == "вул. Тестова, 1"


@pytest.mark.django_db
def test_delivery_map_link_uses_coordinates(client: Client):
    response = client.get(reverse("pages:delivery"))
    assert response.status_code == 200
    content = response.content.decode()
    assert store_maps_url() in content
    assert "maps.google.com/?q=%D0%BF%D1%80%D0%BE%D1%81%D0%BF%D0%B5%D0%BA%D1%82" not in content


@pytest.mark.django_db
def test_contact_page_shows_map_and_address(client: Client):
    response = client.get(reverse("pages:contact"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "проспект Незалежності, 26" in content
    assert store_maps_url() in content
    assert store_maps_embed_url() in content
