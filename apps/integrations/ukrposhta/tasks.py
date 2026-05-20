"""Ukrposhta Celery tasks."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def create_up_shipment_for_order(order_pk: int) -> None:
    """Create Ukrposhta shipment for an order and save barcode."""
    from apps.integrations.ukrposhta.client import UkrPoshtaClient
    from apps.notifications.service import send_notification
    from apps.orders.models import Order

    try:
        order = Order.objects.get(pk=order_pk)
        client = UkrPoshtaClient()
        barcode = client.create_shipment(order)
        if barcode:
            order.up_barcode = barcode
            order.save(update_fields=["up_barcode"])
            logger.info("UP barcode %s saved for order #%s", barcode, order_pk)
            ctx = {"order": order, "ttn": barcode}
            if order.email:
                send_notification("email", order.email, "ttn_created", ctx)
            if order.phone:
                send_notification("sms", order.phone, "ttn_created", ctx)
    except Exception as exc:
        logger.error("create_up_shipment_for_order #%s: %s", order_pk, exc)


@shared_task
def update_up_delivery_statuses() -> None:
    """Periodically check Ukrposhta delivery statuses for active orders."""
    from apps.integrations.ukrposhta.client import UkrPoshtaClient
    from apps.notifications.service import send_notification
    from apps.orders.models import Order, OrderStatus

    client = UkrPoshtaClient()
    orders = (
        Order.objects
        .filter(up_barcode__gt="", delivery_type="ukrposhta")
        .exclude(status__is_completed=True)
        .select_related("status", "customer")
    )

    delivered_status = (
        OrderStatus.objects.filter(is_completed=True).first()
        or OrderStatus.objects.filter(name__icontains="Доставлено").first()
    )

    for order in orders:
        try:
            info = client.track(order.up_barcode)
            if not info:
                continue
            # UkrPoshta statusCode 41 = delivered (UA)
            status_code = str(info.get("eventName", "") or info.get("status", ""))
            is_delivered = "41" in status_code or "DELIVERED" in status_code.upper()

            if is_delivered and delivered_status and order.status_id != delivered_status.pk:
                order.status = delivered_status
                order.save(update_fields=["status"])
                if order.status.notify_customer:
                    if order.email:
                        send_notification(
                            channel="email",
                            recipient=order.email,
                            template_name="order_delivered",
                            context={"order": order, "barcode": order.up_barcode},
                        )
                    if order.phone:
                        send_notification(
                            channel="sms",
                            recipient=order.phone,
                            template_name="order_delivered",
                            context={"order": order, "barcode": order.up_barcode},
                        )
        except Exception as exc:
            logger.error("update_up_delivery_statuses order #%s: %s", order.pk, exc)
