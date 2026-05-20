"""Signals for services app: notify on ServiceRequest status change."""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ServiceRequest

_prev_status: dict[int, str] = {}


@receiver(post_save, sender=ServiceRequest)
def on_repair_status_change(
    sender, instance: ServiceRequest, created: bool, update_fields=None, **kwargs
) -> None:
    if created:
        # Store initial status; optionally notify admin about new request
        _prev_status[instance.pk] = instance.status
        from django.conf import settings
        from apps.notifications.service import send_notification
        if settings.TELEGRAM_ADMIN_CHAT_ID:
            ctx = {
                "req": instance,
                "status_label": instance.get_status_display_uk(),
                "site_phone": getattr(settings, "SITE_PHONE", "+380000000000"),
            }
            send_notification(
                "telegram",
                settings.TELEGRAM_ADMIN_CHAT_ID,
                "repair_status_changed",
                ctx,
            )
        return

    if update_fields and "status" not in update_fields:
        return

    prev = _prev_status.get(instance.pk)
    if prev == instance.status:
        return
    _prev_status[instance.pk] = instance.status

    from apps.notifications.tasks import notify_repair_status
    notify_repair_status.delay(instance.pk)
