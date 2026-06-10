"""Login form and view error feedback."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_login_wrong_password_shows_error(client, customer_factory) -> None:
    customer_factory(email="user@svitpc.ua", password="correctpass1")
    response = client.post(
        reverse("customers:login"),
        {"username": "user@svitpc.ua", "password": "wrongpass"},
    )
    html = response.content.decode()
    assert response.status_code == 200
    assert "auth-form__alert" in html
    assert "form-error" in html
    assert "Невірний email або пароль." in html


@pytest.mark.django_db
def test_login_empty_fields_show_errors(client) -> None:
    response = client.post(reverse("customers:login"), {"username": "", "password": ""})
    html = response.content.decode()
    assert response.status_code == 200
    assert "auth-form__alert" in html
    assert "form-error" in html
    assert "is-invalid" in html


@pytest.mark.django_db
def test_login_short_username_allowed(client, customer_factory) -> None:
    customer_factory(email="admin@svitpc.ua", password="adminpass1")
    response = client.post(
        reverse("customers:login"),
        {"username": "admin", "password": "wrongpass"},
    )
    html = response.content.decode()
    assert response.status_code == 200
    assert "Невірний email або пароль." in html
