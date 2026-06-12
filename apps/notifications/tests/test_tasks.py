"""Tests for order notification Celery tasks."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest


@pytest.mark.django_db
def test_notify_new_order_emails_site_owner(settings, mailoutbox):
    from apps.core.models import SiteSettings
    from apps.notifications.tasks import notify_new_order
    from apps.orders.models import Order, OrderItem, OrderStatus

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "orders@svitpc.com.ua"

    site = SiteSettings.load()
    site.email = "owner@svitpc.com.ua"
    site.save()

    status = OrderStatus.objects.create(name="Новий")
    order = Order.objects.create(
        status=status,
        first_name="Іван",
        last_name="Петренко",
        phone="+380501234567",
        total=Decimal("1500.00"),
    )
    OrderItem.objects.create(
        order=order,
        name="Мишка Logitech",
        sku="MOUSE-1",
        price=Decimal("1500.00"),
        qty=1,
    )

    with patch("apps.notifications.dispatch.send_notification") as mock_send:
        notify_new_order(order.pk)

    owner_calls = [
        c for c in mock_send.call_args_list
        if c.args[:3] == ("email", "owner@svitpc.com.ua", "order_created_admin")
    ]
    assert len(owner_calls) == 1

    telegram_calls = [c for c in mock_send.call_args_list if c.args[0] == "telegram"]
    assert telegram_calls == []


@pytest.mark.django_db
def test_notify_new_order_sends_owner_email_via_mail(settings, mailoutbox):
    from apps.core.models import SiteSettings
    from apps.notifications.tasks import notify_new_order
    from apps.orders.models import Order, OrderStatus

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "orders@svitpc.com.ua"
    settings.SITE_URL = "https://svitpc.com.ua"

    site = SiteSettings.load()
    site.email = "owner@svitpc.com.ua"
    site.save()

    status = OrderStatus.objects.create(name="Новий")
    order = Order.objects.create(
        status=status,
        first_name="Марія",
        last_name="Кoval",
        phone="+380671234567",
        total=Decimal("500.00"),
    )

    notify_new_order(order.pk)

    assert len(mailoutbox) == 1
    msg = mailoutbox[0]
    assert msg.to == ["owner@svitpc.com.ua"]
    assert f"#{order.pk}" in msg.subject
    assert "Марія" in msg.alternatives[0][0]
