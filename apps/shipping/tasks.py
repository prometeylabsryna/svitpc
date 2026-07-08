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


@shared_task(bind=True, queue="priority", max_retries=3, default_retry_delay=60)
def create_ttn_for_order(self, order_pk: int) -> str | None:
    """Create Nova Poshta TTN. Returns error message on failure, None on success.

    Помилка API (валідація даних) — зберігається в Order.shipping_error без retry;
    неочікуваний виняток (мережа) — Celery retry ×3 з паузою 60 с.
    """
    from django.db import transaction

    from apps.integrations.novaposhta.client import NovaPoshtaClient
    from apps.notifications.dispatch import notify_order_customer
    from apps.orders.models import Order
    from apps.shipping.dispatch import order_ready_for_shipment

    ttn = None
    error = ""
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order_pk)
            if order.ttn:
                return None
            if not order_ready_for_shipment(order):
                logger.info("create_ttn_for_order #%s: skipped (not ready for shipment)", order_pk)
                return None
            client = NovaPoshtaClient()
            ttn, error = client.create_ttn(order)
            if ttn:
                order.ttn = ttn
                order.shipping_error = ""
                order.save(update_fields=["ttn", "shipping_error"])
            elif error:
                # Помилка даних (refs, ім'я, оплата) — retry не допоможе;
                # показуємо в адмінці, менеджер виправляє і перезапускає
                logger.error("create_ttn_for_order #%s: %s", order_pk, error)
                order.shipping_error = error[:500]
                order.save(update_fields=["shipping_error"])
                return error
    except Order.DoesNotExist:
        return None
    except Exception as exc:
        logger.error("create_ttn_for_order #%s: %s (retry %s/3)", order_pk, exc, self.request.retries)
        raise self.retry(exc=exc)

    if ttn:
        try:
            order = Order.objects.get(pk=order_pk)
            notify_order_customer(order, "ttn_created", extra_context={"ttn": ttn})
        except Exception as exc:
            logger.error("create_ttn_for_order notify #%s: %s", order_pk, exc)
    return None
