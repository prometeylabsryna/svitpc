"""Shared shipping helpers for checkout and orders."""

from __future__ import annotations

from decimal import Decimal

from apps.catalog.models import Product

DEFAULT_PARCEL_WEIGHT_KG = 0.5
DEFAULT_PARCEL_LENGTH_CM = 30
DEFAULT_PARCEL_WIDTH_CM = 20
DEFAULT_PARCEL_HEIGHT_CM = 10


def cart_weight_kg(cart) -> float:
    """Estimate cart weight in kg for delivery pricing."""
    product_ids = [item["product_id"] for item in cart]
    products = Product.objects.in_bulk(product_ids)
    total = 0.0
    for item in cart:
        product = products.get(item["product_id"])
        unit_weight = float(getattr(product, "weight", 0) or DEFAULT_PARCEL_WEIGHT_KG)
        total += unit_weight * int(item["qty"])
    return total or DEFAULT_PARCEL_WEIGHT_KG


def order_weight_kg(order) -> float:
    """Estimate order weight in kg for delivery pricing."""
    total = 0.0
    for item in order.items.select_related("product").all():
        unit_weight = float(getattr(item.product, "weight", 0) or DEFAULT_PARCEL_WEIGHT_KG)
        total += unit_weight * item.qty
    return total or DEFAULT_PARCEL_WEIGHT_KG


def build_delivery_context(step1: dict, cart, subtotal: Decimal) -> dict:
    """Build delivery cost and payable total for checkout templates."""
    from apps.shipping.services import calc_delivery_cost

    delivery_type = step1.get("delivery_type", "nova_poshta")
    delivery_cost = calc_delivery_cost(
        delivery_type=delivery_type,
        city_ref=step1.get("city_ref", ""),
        warehouse_ref=step1.get("warehouse_ref", ""),
        postcode=step1.get("postcode", ""),
        weight_kg=cart_weight_kg(cart),
        declared_value=subtotal,
    )
    return {
        "delivery_cost": delivery_cost,
        "payable_total": (subtotal + delivery_cost).quantize(Decimal("0.01")),
    }
