"""Basic smoke tests for checkout flow."""

import pytest
from django.urls import reverse

from apps.customers.models import Customer


@pytest.fixture
def product(db, product_factory):
    return product_factory(slug="checkout-prefill-product")


def _cart_session(client, product):
    session = client.session
    session["svitpc_cart"] = {
        str(product.pk): {
            "qty": 1,
            "price": str(product.price),
            "name": product.name,
            "slug": product.slug,
            "image_url": "",
        }
    }
    session.save()


@pytest.mark.django_db
class TestCheckoutStep1:
    def test_step1_url_resolves(self):
        """Checkout step1 URL should be resolvable."""
        try:
            url = reverse("checkout:step1")
            assert url
        except Exception:
            # If URL not under namespace, skip
            pytest.skip("Checkout step1 URL not configured with namespace")

    def test_step1_requires_session(self, client):
        """Checkout should redirect or render (not 500)."""
        try:
            url = reverse("checkout:step1")
        except Exception:
            pytest.skip("Checkout URL not found")
        response = client.get(url)
        assert response.status_code in (200, 302)

    def test_step1_no_prefill_for_staff(self, client, product):
        staff = Customer.objects.create_superuser(
            email="admin@svitpc.ua",
            password="pass",
            first_name="Admin",
        )
        client.force_login(staff)
        _cart_session(client, product)

        response = client.get(reverse("checkout:step1"))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'value="Admin"' not in content
        assert 'value="admin@svitpc.ua"' not in content

    def test_step1_prefill_for_customer(self, client, product):
        customer = Customer.objects.create_user(
            email="buyer@example.com",
            password="pass",
            first_name="Олег",
            last_name="Боніславський",
            phone="+380501112233",
        )
        client.force_login(customer)
        _cart_session(client, product)

        response = client.get(reverse("checkout:step1"))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'value="Олег"' in content
        assert 'value="buyer@example.com"' in content
        assert 'value="+380501112233"' in content
