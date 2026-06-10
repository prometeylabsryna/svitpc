"""Registration modal — invalid POST must return field errors in HTML."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_register_modal_missing_first_name_shows_error(client) -> None:
    response = client.post(
        reverse("customers:register_modal"),
        {
            "next": "/",
            "email": "nick@gmail.com",
            "phone": "0954390000",
            "birth_date": "2003-02-20",
            "password1": "newnewnew6",
            "password2": "newnewnew6",
        },
        HTTP_HX_REQUEST="true",
    )
    html = response.content.decode()
    assert response.status_code == 200
    assert "modal_first_name" in html
    assert "is-invalid" in html
    assert "form-error" in html


@pytest.mark.django_db
def test_register_modal_duplicate_email_shows_error(client) -> None:
    from apps.customers.models import Customer

    Customer.objects.create_user(
        email="nick@gmail.com",
        password="existingpass1",
        first_name="Existing",
        phone="+380501234567",
    )
    response = client.post(
        reverse("customers:register_modal"),
        {
            "next": "/",
            "email": "nick@gmail.com",
            "first_name": "Nick",
            "phone": "0954390000",
            "birth_date": "2003-02-20",
            "password1": "newnewnew6",
            "password2": "newnewnew6",
        },
        HTTP_HX_REQUEST="true",
    )
    html = response.content.decode()
    assert response.status_code == 200
    assert "form-error" in html
    assert "modal_email" in html and "is-invalid" in html


@pytest.mark.django_db
def test_register_modal_shows_errors_on_invalid_post(client) -> None:
    response = client.post(
        reverse("customers:register_modal"),
        {
            "next": "/",
            "email": "bad@example.com",
            "first_name": "Test",
            "phone": "123",
            "birth_date": "20.02.2003",
            "password1": "short",
            "password2": "short",
        },
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert "auth-form__alert" in html
    assert "form-error" in html
    assert "is-invalid" in html
