"""Serial number lookup and warranty helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.catalog.models import Product

from .warranty_models import ProductSerial


@dataclass(frozen=True)
class SerialLookupResult:
    found: bool
    serial_number: str
    product_id: int | None
    product_name: str
    product_code: str
    articul: str
    sale_document: str
    sale_date: date | None
    warranty_until: date | None
    is_under_warranty: bool | None
    warranty_status_label: str
    product_serial_id: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "serial_number": self.serial_number,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "product_code": self.product_code,
            "articul": self.articul,
            "sale_document": self.sale_document,
            "sale_date": self.sale_date.isoformat() if self.sale_date else "",
            "warranty_until": self.warranty_until.isoformat() if self.warranty_until else "",
            "is_under_warranty": self.is_under_warranty,
            "warranty_status_label": self.warranty_status_label,
            "product_serial_id": self.product_serial_id,
        }


def normalize_serial(value: str) -> str:
    return value.strip().upper()


def warranty_status(warranty_until: date | None) -> tuple[bool | None, str]:
    if warranty_until is None:
        return None, ""
    today = timezone.localdate()
    if warranty_until >= today:
        return True, str(_("Товар гарантійний"))
    return False, str(_("Гарантія закінчилась"))


def lookup_serial(raw_serial: str) -> SerialLookupResult:
    """Find product/sale data by serial number in local registry."""
    serial = normalize_serial(raw_serial)
    empty = SerialLookupResult(
        found=False,
        serial_number=serial,
        product_id=None,
        product_name="",
        product_code="",
        articul="",
        sale_document="",
        sale_date=None,
        warranty_until=None,
        is_under_warranty=None,
        warranty_status_label="",
        product_serial_id=None,
    )
    if not serial:
        return empty

    record = (
        ProductSerial.objects.select_related("product")
        .filter(serial_number__iexact=serial)
        .first()
    )
    if not record:
        return empty

    product = record.product
    under, label = warranty_status(record.warranty_until)
    return SerialLookupResult(
        found=True,
        serial_number=record.serial_number,
        product_id=product.pk if product else None,
        product_name=record.product_name or (product.name if product else ""),
        product_code=record.product_code or (product.external_id if product else ""),
        articul=record.articul or (product.sku if product else ""),
        sale_document=record.sale_document,
        sale_date=record.sale_date,
        warranty_until=record.warranty_until,
        is_under_warranty=under,
        warranty_status_label=label,
        product_serial_id=record.pk,
    )


def search_products(query: str, *, limit: int = 10) -> list[Product]:
    q = query.strip()
    if len(q) < 2:
        return []
    return list(
        Product.objects.filter(is_visible=True)
        .filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(external_id__icontains=q))
        .order_by("name")[:limit]
    )


def product_to_lookup_payload(product: Product) -> dict[str, Any]:
    return {
        "product_id": product.pk,
        "product_name": product.name,
        "product_code": product.external_id,
        "articul": product.sku,
    }
