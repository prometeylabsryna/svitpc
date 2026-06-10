"""Registration modal (HTMX) tests."""

import json
from datetime import date

import pytest
from django.urls import reverse

from apps.catalog.models import Product
from apps.customers.models import Customer


@pytest.fixture
def product(db) -> Product:
    return Product.objects.create(name="Товар", slug="modal-reg-product", price=50)


@pytest.mark.django_db
def test_register_modal_success_updates_ui(client, product: Product) -> None:
    next_url = f"/product/{product.slug}/#reviews"
    response = client.post(
        reverse("customers:register_modal"),
        {
            "next": next_url,
            "product_id": product.pk,
            "email": "modal@svitpc.ua",
            "first_name": "Модал",
            "phone": "+380671234567",
            "birth_date": date(1990, 1, 15),
            "password1": "Str0ngPass!",
            "password2": "Str0ngPass!",
        },
        HTTP_HX_REQUEST="true",
    )
    html = response.content.decode()
    assert response.status_code == 200
    assert response["HX-Reswap"] == "none"
    assert 'id="header-account"' in html
    assert 'hx-swap-oob="outerHTML"' in html
    assert 'id="reviews-container"' in html
    assert "review-form" in html
    assert "review-form--guest" not in html
    assert Customer.objects.filter(email="modal@svitpc.ua").exists()
    assert client.session.get("_auth_user_id")

    trigger = json.loads(response["HX-Trigger"])
    assert trigger["modalClose"] is True
    assert trigger["toast"]["type"] == "success"
    assert "Модал" in trigger["toast"]["message"]


@pytest.mark.django_db
def test_register_modal_success_without_product_id(client) -> None:
    response = client.post(
        reverse("customers:register_modal"),
        {
            "next": reverse("customers:dashboard"),
            "email": "noprod@svitpc.ua",
            "first_name": "Без",
            "phone": "+380671234567",
            "birth_date": date(1990, 1, 15),
            "password1": "Str0ngPass!",
            "password2": "Str0ngPass!",
        },
        HTTP_HX_REQUEST="true",
    )
    html = response.content.decode()
    assert response.status_code == 200
    assert 'id="header-account"' in html
    assert "reviews-container" not in html
    assert client.session.get("_auth_user_id")


@pytest.mark.django_db
def test_register_modal_normalizes_absolute_next(client, product: Product) -> None:
    next_url = f"http://testserver/product/{product.slug}/#reviews"
    response = client.post(
        reverse("customers:register_modal"),
        {
            "next": next_url,
            "product_id": product.pk,
            "email": "abs@svitpc.ua",
            "first_name": "Абс",
            "phone": "+380671234567",
            "birth_date": date(1990, 1, 15),
            "password1": "Str0ngPass!",
            "password2": "Str0ngPass!",
        },
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert client.session.get("_auth_user_id")


@pytest.mark.django_db
def test_register_modal_welcome_message_ascii_json_for_cyrillic_name(client) -> None:
    """HX-Trigger JSON must stay ASCII (Django RFC 2047 encodes non-ASCII headers)."""
    product = Product.objects.create(
        name="3D принтер",
        slug="3d-принтер-тест",
        price=100,
    )
    response = client.post(
        reverse("customers:register_modal"),
        {
            "next": f"/product/{product.slug}/#reviews",
            "product_id": product.pk,
            "email": "cyrillic@svitpc.ua",
            "first_name": "Кирилиця",
            "phone": "+380671234567",
            "birth_date": date(1990, 1, 15),
            "password1": "Str0ngPass!",
            "password2": "Str0ngPass!",
        },
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    raw = response["HX-Trigger"]
    assert raw.isascii()
    trigger = json.loads(raw)
    assert "Кирилиця" in trigger["toast"]["message"]


@pytest.mark.django_db
def test_register_modal_rejects_external_next(client) -> None:
    response = client.post(
        reverse("customers:register_modal"),
        {
            "next": "https://evil.example/phish",
            "email": "evil@svitpc.ua",
            "first_name": "Evil",
            "phone": "+380671234567",
            "birth_date": date(1990, 1, 15),
            "password1": "Str0ngPass!",
            "password2": "Str0ngPass!",
        },
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert "evil.example" not in response.content.decode()
    assert Customer.objects.filter(email="evil@svitpc.ua").exists()
