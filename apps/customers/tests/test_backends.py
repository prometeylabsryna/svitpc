import pytest
from django.contrib.auth import authenticate

from apps.customers.models import Customer


@pytest.mark.django_db
def test_short_admin_login() -> None:
    Customer.objects.create_superuser(
        email="admin@svitpc.ua",
        password="admin",
        first_name="Admin",
    )
    assert authenticate(username="admin", password="admin") is not None
    assert authenticate(username="admin@svitpc.ua", password="admin") is not None
    assert authenticate(username="admin", password="wrong") is None
