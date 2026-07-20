"""Safe parsing of catalog listing GET params (filters, price, page)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.http import HttpRequest


def parse_decimal_param(raw: str | None) -> Decimal | None:
    """Parse price-like GET value; accept comma decimal; ignore junk (no 500)."""
    if raw is None:
        return None
    text = str(raw).strip().replace(" ", "").replace(",", ".")
    if not text:
        return None
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if value < 0:
        return None
    return value


def parse_page_param(raw: str | None, *, default: int = 1) -> int:
    try:
        page = int(raw or default)
    except (TypeError, ValueError):
        return default
    return max(1, page)


def parse_in_stock_param(raw: str | None) -> bool:
    """Only explicit truthy flags count — ``?in_stock=0`` must be False."""
    if raw is None:
        return False
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def parse_catalog_list_filters(request: HttpRequest) -> dict[str, Any]:
    """Common GET parsing for category/brand listing views."""
    brand_ids = [int(x) for x in request.GET.getlist("brand") if x.isdigit()]
    filter_ids = [int(x) for x in request.GET.getlist("f") if x.isdigit()]
    return {
        "brand_ids": brand_ids,
        "filter_ids": filter_ids,
        "price_min": parse_decimal_param(request.GET.get("price_min")),
        "price_max": parse_decimal_param(request.GET.get("price_max")),
        "sort": request.GET.get("sort") or "default",
        "in_stock": parse_in_stock_param(request.GET.get("in_stock")),
        "page": parse_page_param(request.GET.get("page")),
    }
