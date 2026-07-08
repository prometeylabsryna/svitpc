"""Order signals: accrue loyalty bonuses + fiscal receipt when order is paid/completed."""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Order, OrderHistory

logger = logging.getLogger(__name__)


def schedule_coin_accrual(order_pk: int) -> None:
    """Credit loyalty coins after the DB transaction commits (no Celery required)."""

    def _accrue() -> None:
        from apps.loyalty.coins import accrue_coins_for_order

        try:
            order = Order.objects.select_related("customer").get(pk=order_pk)
            accrue_coins_for_order(order)
        except Exception:
            logger.exception("Coin accrual failed for order #%s", order_pk)

    transaction.on_commit(_accrue)


@receiver(post_save, sender=Order)
def on_order_created(sender, instance: Order, created: bool, **kwargs) -> None:
    """Notify store owner via email when a new order is placed."""
    if not created:
        return

    def _enqueue() -> None:
        from apps.core.celery_utils import safe_delay
        from apps.notifications.tasks import notify_new_order_customer, notify_new_order_owner

        # Owner email first (fast); customer SMS/push in a separate task.
        # safe_delay: падіння брокера не має ламати створення замовлення.
        safe_delay(notify_new_order_owner, instance.pk)
        safe_delay(notify_new_order_customer, instance.pk)

    transaction.on_commit(_enqueue)


@receiver(post_save, sender=Order)
def on_order_status_change(sender, instance: Order, created: bool, update_fields=None, **kwargs) -> None:
    """Accrue loyalty bonuses when order reaches a completed status."""
    if created:
        return
    if update_fields and "status_id" not in update_fields and "status" not in update_fields:
        return
    if not instance.status_id:
        return
    if not instance.status.is_completed:
        return
    schedule_coin_accrual(instance.pk)


@receiver(post_save, sender=Order)
def on_order_status_notify(sender, instance: Order, created: bool, update_fields=None, **kwargs) -> None:
    """Notify customer (email/Telegram/push) when order status changes."""
    if created:
        return
    if update_fields and "status_id" not in update_fields and "status" not in update_fields:
        return
    if not instance.status_id:
        return
    from apps.core.celery_utils import safe_delay
    from apps.notifications.tasks import notify_order_status

    safe_delay(notify_order_status, instance.pk)


@receiver(post_save, sender=Order)
def on_order_paid(sender, instance: Order, created: bool, update_fields=None, **kwargs) -> None:
    """Fiscalize paid orders and dispatch carrier shipments when ready."""
    from django.db import transaction

    from apps.shipping.dispatch import dispatch_shipment_for_order

    def _dispatch() -> None:
        dispatch_shipment_for_order(instance.pk)

    if created:
        if instance.payment_method == Order.PAYMENT_CASH_ON_DELIVERY:
            transaction.on_commit(_dispatch)
        return

    if update_fields and "is_paid" not in update_fields:
        return
    if not instance.is_paid:
        return

    transaction.on_commit(_dispatch)

    if instance.fiscal_check_url:
        return

    def _fiscalize() -> None:
        # Через Celery (черга priority, retry×3) — не блокує webhook-запит
        # і переживає тимчасові збої API Вчасно.Каса.
        from apps.core.celery_utils import safe_delay
        from apps.integrations.vchasnokasa.tasks import fiscalize_payment

        safe_delay(fiscalize_payment, instance.pk)

    transaction.on_commit(_fiscalize)


@receiver(post_save, sender=Order)
def on_order_delivery_updated(
    sender, instance: Order, created: bool, update_fields=None, **kwargs
) -> None:
    """Queue TTN when admin fills Nova Poshta delivery after order was created."""
    if created:
        return
    if instance.delivery_type != Order.DELIVERY_NP or instance.ttn:
        return

    delivery_fields = {"delivery_type", "city_ref", "warehouse_ref", "city", "warehouse"}
    if update_fields and not delivery_fields.intersection(update_fields):
        return
    if not instance.city_ref or not instance.warehouse_ref:
        return

    from apps.shipping.dispatch import dispatch_shipment_for_order, order_ready_for_shipment

    if not order_ready_for_shipment(instance):
        return

    transaction.on_commit(lambda: dispatch_shipment_for_order(instance.pk))


@receiver(pre_save, sender=Order)
def order_cache_previous_status(sender, instance: Order, **kwargs) -> None:
    if instance.pk:
        instance._previous_status_id = (
            Order.objects.filter(pk=instance.pk).values_list("status_id", flat=True).first()
        )
    else:
        instance._previous_status_id = None


@receiver(post_save, sender=Order)
def on_order_created_history(sender, instance: Order, created: bool, **kwargs) -> None:
    """Create an initial status history row for new orders."""
    if not created:
        return
    OrderHistory.objects.get_or_create(
        order=instance,
        status=instance.status,
        defaults={"comment": "", "notify_customer": False},
    )


@receiver(post_save, sender=Order)
def on_order_status_history(sender, instance: Order, created: bool, **kwargs) -> None:
    """Mirror Order.status changes into OrderHistory for the admin audit trail."""
    if created:
        return
    previous = getattr(instance, "_previous_status_id", None)
    if previous is None or previous == instance.status_id:
        return
    latest = instance.history.order_by("-created_at", "-pk").first()
    if latest and latest.status_id == instance.status_id:
        return
    OrderHistory.objects.create(
        order=instance,
        status=instance.status,
        comment="",
        notify_customer=False,
    )
