"""Tests for customer welcome helpers."""

import pytest

from apps.customers.utils import customer_display_name, customer_welcome_message


@pytest.mark.django_db
def test_customer_welcome_message_uses_first_name(customer_factory):
    customer = customer_factory(first_name="Олег", email="oleg@example.com")
    assert customer_display_name(customer) == "Олег"
    assert customer_welcome_message(customer) == "Вітаю, Олег!"


@pytest.mark.django_db
def test_customer_welcome_message_falls_back_to_email(customer_factory):
    customer = customer_factory(first_name="", email="buyer@example.com")
    assert customer_display_name(customer) == "buyer"
    assert "buyer" in customer_welcome_message(customer)
