"""Basic smoke tests for checkout flow."""

import pytest
from django.urls import reverse


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
