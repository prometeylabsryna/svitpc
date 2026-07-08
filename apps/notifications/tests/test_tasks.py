"""Tests for order notification Celery tasks."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import transaction


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


@pytest.mark.django_db
def test_notify_new_order_owner_before_customer(settings):
    from apps.core.models import SiteSettings
    from apps.notifications.tasks import notify_new_order
    from apps.orders.models import Order, OrderStatus

    site = SiteSettings.load()
    site.email = "owner@svitpc.com.ua"
    site.save()

    status = OrderStatus.objects.create(name="Новий")
    order = Order.objects.create(
        status=status,
        first_name="Тест",
        phone="+380501234567",
        total=Decimal("100.00"),
    )

    call_order: list[str] = []

    def track_send(channel, recipient, template, ctx=None):
        call_order.append(f"{channel}:{template}")
        return True

    with patch("apps.notifications.dispatch.send_notification", side_effect=track_send):
        notify_new_order(order.pk)

    assert call_order[0] == "email:order_created_admin"
    assert any(c.startswith("email:order_created") or c.startswith("sms:") for c in call_order[1:])


@pytest.mark.django_db
def test_on_order_created_enqueues_after_commit(django_capture_on_commit_callbacks):
    from apps.orders.models import Order, OrderStatus

    status = OrderStatus.objects.create(name="Новий")

    with patch("apps.notifications.tasks.notify_new_order_owner.delay") as owner_delay, patch(
        "apps.notifications.tasks.notify_new_order_customer.delay",
    ) as customer_delay:
        with django_capture_on_commit_callbacks(execute=True):
            with transaction.atomic():
                Order.objects.create(
                    status=status,
                    first_name="Олег",
                    phone="+380671111111",
                    total=Decimal("200.00"),
                )
            owner_delay.assert_not_called()
            customer_delay.assert_not_called()

    owner_delay.assert_called_once()
    customer_delay.assert_called_once()


def test_order_notify_tasks_use_priority_queue():
    from apps.notifications.tasks import (
        notify_new_order_customer,
        notify_new_order_owner,
        notify_order_status,
    )

    assert notify_new_order_owner.queue == "priority"
    assert notify_new_order_customer.queue == "priority"
    assert notify_order_status.queue == "priority"
    assert notify_new_order_owner.max_retries == 3


@pytest.mark.django_db
def test_notify_new_order_owner_retries_when_email_fails(settings):
    from apps.core.models import SiteSettings
    from apps.notifications.tasks import notify_new_order_owner
    from apps.orders.models import Order, OrderStatus

    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True

    site = SiteSettings.load()
    site.email = "owner@svitpc.com.ua"
    site.save()

    status = OrderStatus.objects.create(name="Новий")
    order = Order.objects.create(
        status=status,
        first_name="Тест",
        phone="+380501234567",
        total=Decimal("100.00"),
    )

    with patch("apps.notifications.tasks.notify_site_owner", return_value=False), patch.object(
        notify_new_order_owner,
        "retry",
        side_effect=RuntimeError("retry called"),
    ) as mock_retry:
        with pytest.raises(RuntimeError, match="retry called"):
            notify_new_order_owner(order.pk)

    mock_retry.assert_called_once()
