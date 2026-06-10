"""Registration form validation tests."""

from datetime import date, timedelta

import pytest

from apps.customers.forms import CustomerRegistrationForm


@pytest.mark.django_db
def test_registration_requires_phone_and_birth_date():
    form = CustomerRegistrationForm(
        {
            "email": "new@svitpc.ua",
            "first_name": "Новий",
            "password1": "Str0ngPass!",
            "password2": "Str0ngPass!",
        }
    )
    assert not form.is_valid()
    assert "phone" in form.errors
    assert "birth_date" in form.errors


@pytest.mark.django_db
def test_registration_valid_with_required_fields():
    form = CustomerRegistrationForm(
        {
            "email": "valid@svitpc.ua",
            "first_name": "Валід",
            "phone": "+380671234567",
            "birth_date": date(1995, 5, 20),
            "password1": "Str0ngPass!",
            "password2": "Str0ngPass!",
        }
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_registration_accepts_simple_password():
    form = CustomerRegistrationForm(
        {
            "email": "simple@svitpc.ua",
            "first_name": "Простий",
            "phone": "+380671234567",
            "birth_date": date(1990, 1, 1),
            "password1": "123456789",
            "password2": "123456789",
        }
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_registration_rejects_short_password():
    form = CustomerRegistrationForm(
        {
            "email": "short@svitpc.ua",
            "first_name": "Короткий",
            "phone": "+380671234567",
            "birth_date": date(1990, 1, 1),
            "password1": "1234567",
            "password2": "1234567",
        }
    )
    assert not form.is_valid()
    assert "password2" in form.errors


@pytest.mark.django_db
def test_registration_rejects_future_birth_date():
    form = CustomerRegistrationForm(
        {
            "email": "future@svitpc.ua",
            "first_name": "Майбутнє",
            "phone": "+380671234567",
            "birth_date": date.today() + timedelta(days=1),
            "password1": "Str0ngPass!",
            "password2": "Str0ngPass!",
        }
    )
    assert not form.is_valid()
    assert "birth_date" in form.errors
