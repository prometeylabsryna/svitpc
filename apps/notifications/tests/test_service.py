"""Tests for notification service — channel routing + fallback."""
from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_unknown_channel_returns_false():
    from apps.notifications.service import send_notification
    result = send_notification("unknown_channel", "test@test.com", "test_template")
    assert result is False


@pytest.mark.django_db
def test_email_channel(settings, mailoutbox):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "noreply@svitpc.ua"
    from apps.notifications.service import send_notification
    result = send_notification("email", "user@test.com", "nonexistent_template")
    assert isinstance(result, bool)


@pytest.mark.django_db
def test_sms_no_key_returns_false(settings):
    settings.SMS_API_KEY = ""
    from apps.notifications.service import send_notification
    result = send_notification("sms", "+380000000000", "order_status")
    assert result is False


@pytest.mark.django_db
def test_viber_no_token_returns_false(settings):
    settings.VIBER_BOT_TOKEN = ""
    from apps.notifications.service import send_notification
    result = send_notification("viber", "user_viber_id", "order_status")
    assert result is False


@pytest.mark.django_db
def test_telegram_no_token_returns_false(settings):
    settings.TELEGRAM_BOT_TOKEN = ""
    from apps.notifications.service import send_notification
    result = send_notification("telegram", "12345678", "order_status")
    assert result is False


@pytest.mark.django_db
def test_push_no_vapid_key_returns_false(settings):
    settings.VAPID_PRIVATE_KEY = ""
    from apps.notifications.service import send_notification
    result = send_notification("push", 1, "order_created", {"title": "T", "body": "B"})
    assert result is False


@pytest.mark.django_db
def test_push_no_subscriptions_returns_false(settings, django_user_model):
    settings.VAPID_PRIVATE_KEY = "fake-key"
    settings.VAPID_CLAIMS_EMAIL = "admin@svitpc.ua"
    user = django_user_model.objects.create_user(email="pushtest@test.com", password="pw")
    from apps.notifications.service import send_notification
    # No subscriptions → False
    result = send_notification("push", user.pk, "order_created", {"title": "T", "body": "B"})
    assert result is False


@pytest.mark.django_db
def test_push_stale_subscription_deleted(settings, django_user_model):
    """Stale subscription (simulated via mocked webpush raising 410) must be removed."""
    from unittest.mock import MagicMock, patch

    settings.VAPID_PRIVATE_KEY = "fake-key"
    settings.VAPID_CLAIMS_EMAIL = "admin@svitpc.ua"
    user = django_user_model.objects.create_user(email="staletest@test.com", password="pw")

    from apps.notifications.models import PushSubscription

    sub = PushSubscription.objects.create(
        customer=user,
        endpoint="https://fcm.example.com/token",
        p256dh="p256dh_value",
        auth="auth_value",
    )

    fake_response = MagicMock()
    fake_response.status_code = 410

    from pywebpush import WebPushException

    stale_exc = WebPushException("Gone")
    stale_exc.response = fake_response

    with patch("pywebpush.webpush", side_effect=stale_exc):
        from apps.notifications.service import send_notification
        result = send_notification("push", user.pk, "test", {"title": "T", "body": "B"})

    assert result is False
    assert not PushSubscription.objects.filter(pk=sub.pk).exists()


@pytest.mark.django_db
def test_notify_promotion_push_no_subscribers():
    from apps.notifications.tasks import notify_promotion_push
    from apps.promotions.models import Promotion

    promo = Promotion.objects.create(name="Test Promo", slug="test-promo")
    result = notify_promotion_push(promo.pk)
    assert result == 0


@pytest.mark.django_db
def test_notify_promotion_push_nonexistent():
    from apps.notifications.tasks import notify_promotion_push

    result = notify_promotion_push(99999)
    assert result == 0
