"""Dispatch carrier shipments when an order is ready to ship."""

from __future__ import annotations

import logging

from apps.orders.models import Order

logger = logging.getLogger(__name__)


def order_ready_for_shipment(order: Order) -> bool:
    """Return True when the order should receive a TTN / UP barcode."""
    if order.delivery_type == Order.DELIVERY_PICKUP:
        return False
    if order.delivery_type == Order.DELIVERY_NP and order.ttn:
        return False
    if order.delivery_type == Order.DELIVERY_UP and order.up_barcode:
        return False
    if order.payment_method == Order.PAYMENT_CASH_ON_DELIVERY:
        return True
    return order.is_paid


def dispatch_shipment_for_order(order_pk: int) -> None:
    """Create carrier shipment for a ready order."""
    try:
        order = Order.objects.get(pk=order_pk)
    except Order.DoesNotExist:
        return

    if not order_ready_for_shipment(order):
        return

    if order.delivery_type == Order.DELIVERY_NP:
        from apps.shipping.tasks import create_ttn_for_order

        create_ttn_for_order.delay(order.pk)
    elif order.delivery_type == Order.DELIVERY_UP:
        from apps.integrations.ukrposhta.tasks import create_up_shipment_for_order

        create_up_shipment_for_order.delay(order.pk)
