"""Shipping Celery tasks."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def update_delivery_statuses() -> None:
    """Periodically update Nova Poshta TTN statuses for active orders."""
    from apps.integrations.novaposhta.client import DELIVERED_CODES, NovaPoshtaClient
    from apps.notifications.dispatch import notify_order_customer
    from apps.orders.models import Order, OrderStatus

    client = NovaPoshtaClient()
    orders = (
        Order.objects
        .filter(ttn__gt="", delivery_type="nova_poshta")
        .exclude(status__is_completed=True)
        .select_related("status", "customer")
    )

    delivered_status = (
        OrderStatus.objects.filter(is_completed=True).first()
        or OrderStatus.objects.filter(name__icontains="Доставлено").first()
    )

    for order in orders:
        try:
            info = client.track_ttn(order.ttn)
            if not info:
                continue
            status_code = str(info.get("StatusCode", ""))

            if status_code in DELIVERED_CODES and delivered_status:
                if order.status_id != delivered_status.pk:
                    order.status = delivered_status
                    order.save(update_fields=["status"])
                    if order.status.notify_customer:
                        notify_order_customer(order, "order_delivered", extra_context={"ttn": order.ttn})
        except Exception as exc:
            logger.error("update_delivery_statuses order #%s: %s", order.pk, exc)


@shared_task(queue="priority")
def create_ttn_for_order(order_pk: int) -> None:
    """Create Nova Poshta TTN for an order and notify customer."""
    from django.db import transaction

    from apps.integrations.novaposhta.client import NovaPoshtaClient
    from apps.notifications.dispatch import notify_order_customer
    from apps.orders.models import Order
    from apps.shipping.dispatch import order_ready_for_shipment

    ttn = None
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order_pk)
            if order.ttn:
                return
            if not order_ready_for_shipment(order):
                logger.info("create_ttn_for_order #%s: skipped (not ready for shipment)", order_pk)
                return
            if not order.city_ref or not order.warehouse_ref:
                logger.warning(
                    "create_ttn_for_order #%s: missing city_ref/warehouse_ref",
                    order_pk,
                )
                return
            client = NovaPoshtaClient()
            ttn = client.create_ttn(order)
            if ttn:
                order.ttn = ttn
                order.save(update_fields=["ttn"])
            else:
                logger.error("create_ttn_for_order #%s: Nova Poshta returned no TTN", order_pk)
    except Order.DoesNotExist:
        return
    except Exception as exc:
        logger.error("create_ttn_for_order #%s: %s", order_pk, exc)
        return

    if ttn:
        try:
            order = Order.objects.get(pk=order_pk)
            notify_order_customer(order, "ttn_created", extra_context={"ttn": ttn})
        except Exception as exc:
            logger.error("create_ttn_for_order notify #%s: %s", order_pk, exc)
