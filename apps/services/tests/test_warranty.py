"""Warranty serial lookup and claim form tests."""

from datetime import date, timedelta

import pytest
from django.urls import reverse

from apps.services.forms import WarrantyClaimForm
from apps.services.serial_lookup import lookup_serial, normalize_serial, warranty_status
from apps.services.warranty_models import ProductSerial


@pytest.fixture
def product(product_factory):
    return product_factory()


@pytest.fixture
def staff_user(customer_factory):
    return customer_factory(is_staff=True)


@pytest.fixture
def customer_user(customer_factory):
    return customer_factory(is_staff=False)


@pytest.mark.django_db
def test_normalize_serial_uppercases() -> None:
    assert normalize_serial("  abc-123 ") == "ABC-123"


@pytest.mark.django_db
def test_lookup_serial_found(product) -> None:
    ProductSerial.objects.create(
        serial_number="SN-TEST-001",
        product=product,
        product_name=product.name,
        product_code="U123",
        articul="ART-1",
        sale_document="DOC-1",
        sale_date=date(2026, 1, 1),
        warranty_until=date(2027, 1, 1),
    )
    result = lookup_serial("sn-test-001")
    assert result.found is True
    assert result.product_id == product.pk
    assert result.sale_document == "DOC-1"


@pytest.mark.django_db
def test_warranty_status_active() -> None:
    future = date.today() + timedelta(days=30)
    ok, label = warranty_status(future)
    assert ok is True
    assert "гарантійний" in label.lower()


@pytest.mark.django_db
def test_warranty_claim_form_requires_serial_or_flag() -> None:
    form = WarrantyClaimForm(
        data={
            "serial_number": "",
            "without_serial_number": False,
            "product_name": "Test product",
            "defect_description": "Broken",
        },
    )
    assert not form.is_valid()
    assert "serial_number" in form.errors


@pytest.mark.django_db
def test_warranty_form_public_access(client) -> None:
    resp = client.get(reverse("services:warranty_list"))
    assert resp.status_code == 200
    assert b"warranty-claim-form" in resp.content


@pytest.mark.django_db
def test_warranty_form_delivery_choices() -> None:
    form = WarrantyClaimForm()
    values = {value for value, _label in form.fields["delivery_service"].choices if value}
    assert values == {"nova_poshta", "other"}


@pytest.mark.django_db
def test_warranty_form_submit(client) -> None:
    resp = client.post(
        reverse("services:warranty_list"),
        {
            "serial_number": "SN-PUBLIC-1",
            "product_name": "Test laptop",
            "defect_description": "No power",
            "client_name": "Ivan",
            "client_phone": "+380501234567",
            "client_email": "ivan@example.com",
            "client_address": "Kyiv",
            "action": "submit",
        },
    )
    assert resp.status_code == 200
    assert "warranty-page__success" in resp.content.decode()


@pytest.mark.django_db
def test_serial_lookup_api(client, product) -> None:
    ProductSerial.objects.create(
        serial_number="API-SN-1",
        product=product,
        product_name=product.name,
        warranty_until=date(2028, 1, 1),
    )
    resp = client.get(reverse("services:warranty_serial_lookup"), {"serial": "API-SN-1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["product_name"] == product.name
