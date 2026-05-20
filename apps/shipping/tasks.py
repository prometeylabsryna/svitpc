"""Shipping Celery tasks."""

from __future__ import annotations

from celery import shared_task


@shared_task
def update_delivery_statuses() -> None:
    """Periodically update Nova Poshta TTN statuses for active orders."""
    from apps.integrations.novaposhta.client import NP_STATUS_MAP, DELIVERED_CODES, IN_TRANSIT_CODES, NovaPoshtaClient
    from apps.notifications.service import send_notification
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
            status_text = NP_STATUS_MAP.get(status_code, info.get("Status", ""))

            if status_code in DELIVERED_CODES and delivered_status:
                if order.status_id != delivered_status.pk:
                    order.status = delivered_status
                    order.save(update_fields=["status"])
                    if order.status.notify_customer and order.email:
                        send_notification(
                            channel="email",
                            recipient=order.email,
                            template_name="order_delivered",
                            context={"order": order, "ttn": order.ttn},
                        )
            elif status_code in IN_TRANSIT_CODES and order.status.notify_customer:
                # Notify about transit status update if status changed
                pass  # optional: add OrderHistory tracking here
        except Exception as exc:
            from django.core.exceptions import ObjectDoesNotExist
            import logging
            logging.getLogger(__name__).error("update_delivery_statuses order #%s: %s", order.pk, exc)


@shared_task
def create_ttn_for_order(order_pk: int) -> None:
    """Create Nova Poshta TTN for an order and notify customer."""
    from apps.integrations.novaposhta.client import NovaPoshtaClient
    from apps.notifications.service import send_notification
    from apps.orders.models import Order

    try:
        order = Order.objects.get(pk=order_pk)
        client = NovaPoshtaClient()
        ttn = client.create_ttn(order)
        if ttn:
            order.ttn = ttn
            order.save(update_fields=["ttn"])
            ctx = {"order": order, "ttn": ttn}
            if order.email:
                send_notification("email", order.email, "ttn_created", ctx)
            if order.phone:
                send_notification("sms", order.phone, "ttn_created", ctx)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("create_ttn_for_order #%s: %s", order_pk, exc)
