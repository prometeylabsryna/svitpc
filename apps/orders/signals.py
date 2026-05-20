"""Order signals: accrue loyalty bonuses + fiscal receipt when order is paid/completed."""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Order


@receiver(post_save, sender=Order)
def on_order_created(sender, instance: Order, created: bool, **kwargs) -> None:
    """Notify admin via Telegram when a new order is placed."""
    if not created:
        return
    from apps.notifications.tasks import notify_new_order
    notify_new_order.delay(instance.pk)


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
    from apps.loyalty.tasks import accrue_order_bonuses
    accrue_order_bonuses.delay(instance.pk)


@receiver(post_save, sender=Order)
def on_order_status_notify(sender, instance: Order, created: bool, update_fields=None, **kwargs) -> None:
    """Notify customer (email/Telegram/push) when order status changes."""
    if created:
        return
    if update_fields and "status_id" not in update_fields and "status" not in update_fields:
        return
    if not instance.status_id:
        return
    from apps.notifications.tasks import notify_order_status
    notify_order_status.delay(instance.pk)


@receiver(post_save, sender=Order)
def on_order_paid(sender, instance: Order, created: bool, update_fields=None, **kwargs) -> None:
    """Create Vchasno.Kasa fiscal receipt when order is marked as paid."""
    if created:
        return
    if update_fields and "is_paid" not in update_fields:
        return
    if not instance.is_paid:
        return
    if instance.fiscal_check_url:
        return  # already fiscalized

    from apps.integrations.vchasnokasa.client import VchasnoKasaClient
    try:
        client = VchasnoKasaClient()
        url = client.create_receipt(instance)
        if url:
            Order.objects.filter(pk=instance.pk).update(fiscal_check_url=url)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("on_order_paid fiscal receipt error #%s: %s", instance.pk, exc)
