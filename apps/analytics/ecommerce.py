"""GA4 / dataLayer ecommerce payload helpers."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from apps.core.text import unescape_legacy_html


def _clean_name(value: str | None) -> str:
    return unescape_legacy_html(value or "")


def _price(value: Decimal | float | str | int) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


def product_item(product: Any, *, quantity: int = 1) -> dict[str, Any]:
    """Single GA4 item dict from a Product instance."""
    return {
        "item_id": str(product.pk),
        "item_name": _clean_name(getattr(product, "name", "")),
        "price": _price(product.price),
        "quantity": quantity,
    }


def product_view_payload(product: Any) -> dict[str, Any]:
    return {
        "id": product.pk,
        "name": _clean_name(getattr(product, "name", "")),
        "price": _price(product.price),
    }


def cart_action_payload(
    *, product_id: int, name: str, price: Decimal | str, qty: int,
) -> dict[str, Any]:
    return {
        "id": product_id,
        "name": _clean_name(name),
        "price": _price(price),
        "qty": qty,
    }


def order_purchase_payload(order: Any) -> dict[str, Any]:
    items = []
    for item in order.items.all():
        items.append(
            {
                "item_id": str(item.product_id or item.pk),
                "item_name": _clean_name(item.name),
                "price": _price(item.price),
                "quantity": item.qty,
            }
        )
    return {
        "order_id": str(order.pk),
        "total": _price(order.total),
        "items": items,
    }


def product_list_payload(*, list_id: str, list_name: str, products: list[Any]) -> dict[str, Any]:
    return {
        "list_id": list_id,
        "list_name": _clean_name(list_name),
        "items": [product_item(p) for p in products],
    }


def ecommerce_json(data: dict[str, Any]) -> str:
    """Safe JSON string for HTML meta content attributes."""
    return json.dumps(data, ensure_ascii=False)
