"""Ukrposhta Celery tasks."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue="priority", max_retries=3, default_retry_delay=60)
def create_up_shipment_for_order(self, order_pk: int) -> None:
    """Create Ukrposhta shipment for an order and save barcode."""
    from django.db import transaction

    from apps.integrations.ukrposhta.client import UkrPoshtaClient
    from apps.notifications.dispatch import notify_order_customer
    from apps.orders.models import Order
    from apps.shipping.dispatch import order_ready_for_shipment

    barcode = None
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order_pk)
            if not order_ready_for_shipment(order) or order.up_barcode:
                return
            client = UkrPoshtaClient()
            barcode = client.create_shipment(order)
            if barcode:
                order.up_barcode = barcode
                order.shipping_error = ""
                order.save(update_fields=["up_barcode", "shipping_error"])
                logger.info("UP barcode %s saved for order #%s", barcode, order_pk)
    except Order.DoesNotExist:
        return
    except Exception as exc:
        logger.error(
            "create_up_shipment_for_order #%s: %s (retry %s/3)",
            order_pk, exc, self.request.retries,
        )
        raise self.retry(exc=exc)

    if barcode:
        try:
            order = Order.objects.get(pk=order_pk)
            notify_order_customer(order, "ttn_created", extra_context={"ttn": barcode})
        except Exception as exc:
            logger.error("create_up_shipment_for_order notify #%s: %s", order_pk, exc)


@shared_task
def update_up_delivery_statuses() -> None:
    """Periodically check Ukrposhta delivery statuses for active orders."""
    from apps.integrations.ukrposhta.client import UkrPoshtaClient
    from apps.notifications.dispatch import notify_order_customer
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

            if client.is_delivered(info) and delivered_status and order.status_id != delivered_status.pk:
                order.status = delivered_status
                order.save(update_fields=["status"])
                if order.status.notify_customer:
                    notify_order_customer(
                        order,
                        "order_delivered",
                        extra_context={"ttn": order.up_barcode, "barcode": order.up_barcode},
                    )
        except Exception as exc:
            logger.error("update_up_delivery_statuses order #%s: %s", order.pk, exc)
