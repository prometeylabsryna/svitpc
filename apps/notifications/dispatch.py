"""Shared multi-channel dispatch for order and customer notifications."""

from __future__ import annotations

from typing import Any

from django.conf import settings

from apps.core.models import SiteSettings

from .service import send_notification


def site_url() -> str:
    return getattr(settings, "SITE_URL", "").rstrip("/")


def order_context(order: Any, **extra: Any) -> dict[str, Any]:
    site = SiteSettings.load()
    ctx: dict[str, Any] = {
        "order": order,
        "site_url": site_url(),
        "site_phone": site.phone,
        "site_email": site.email,
        "site_name": site.name,
    }
    ctx.update(extra)
    return ctx


def notify_order_customer(
    order: Any,
    template_name: str,
    *,
    extra_context: dict[str, Any] | None = None,
    push_title: str = "",
    push_body: str = "",
    push_url: str = "",
    push_tag: str = "",
) -> None:
    """Email, SMS, Telegram, Viber, and optional web-push for an order recipient."""
    ctx = order_context(order, **(extra_context or {}))
    customer = getattr(order, "customer", None)

    if order.email:
        send_notification("email", order.email, template_name, ctx)

    phone = ""
    if customer and getattr(customer, "consent_sms", False) and customer.phone:
        phone = customer.phone
    elif order.phone:
        phone = order.phone
    if phone:
        send_notification("sms", phone, template_name, ctx)

    if customer:
        if getattr(customer, "telegram_chat_id", ""):
            send_notification("telegram", customer.telegram_chat_id, template_name, ctx)
        if getattr(customer, "viber_id", ""):
            send_notification("viber", customer.viber_id, template_name, ctx)

    if order.customer_id and push_title:
        send_notification(
            "push",
            order.customer_id,
            template_name,
            {
                "title": push_title,
                "body": push_body,
                "url": push_url or order.get_absolute_url(),
                "tag": push_tag or f"order-{order.pk}",
            },
        )


def notify_customer_channels(
    customer: Any,
    template_name: str,
    context: dict[str, Any],
) -> None:
    """Email, SMS, Telegram, and Viber for a registered customer."""
    if getattr(customer, "consent_email", False) and customer.email:
        send_notification("email", customer.email, template_name, context)
    if getattr(customer, "consent_sms", False) and customer.phone:
        send_notification("sms", customer.phone, template_name, context)
    if getattr(customer, "telegram_chat_id", ""):
        send_notification("telegram", customer.telegram_chat_id, template_name, context)
    if getattr(customer, "viber_id", ""):
        send_notification("viber", customer.viber_id, template_name, context)
