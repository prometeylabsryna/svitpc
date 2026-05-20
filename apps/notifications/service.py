"""Unified notification router: email / SMS / Telegram / Viber / web-push."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

CHANNELS = {"email", "sms", "telegram", "viber", "push"}


def send_notification(
    channel: str,
    recipient: str,
    template_name: str,
    context: dict | None = None,
) -> bool:
    """Route notification to the appropriate channel."""
    ctx = context or {}
    if channel not in CHANNELS:
        logger.warning("Unknown notification channel: %s", channel)
        return False

    try:
        if channel == "email":
            return _send_email(recipient, template_name, ctx)
        elif channel == "sms":
            return _send_sms(recipient, template_name, ctx)
        elif channel == "telegram":
            return _send_telegram(recipient, template_name, ctx)
        elif channel == "viber":
            return _send_viber(recipient, template_name, ctx)
        elif channel == "push":
            return _send_push(recipient, template_name, ctx)
    except Exception as exc:
        logger.exception("Notification error channel=%s template=%s: %s", channel, template_name, exc)
    return False


def _send_email(to: str, template: str, ctx: dict) -> bool:
    subject_tpl = f"email/{template}_subject.txt"
    body_tpl = f"email/{template}_body.html"
    try:
        subject = render_to_string(subject_tpl, ctx).strip()
        body = render_to_string(body_tpl, ctx)
    except Exception:
        subject = "СвітПК — повідомлення"
        body = str(ctx)
    send_mail(subject, "", settings.DEFAULT_FROM_EMAIL, [to], html_message=body, fail_silently=False)
    return True


def _send_sms(phone: str, template: str, ctx: dict) -> bool:
    """Send SMS via TurboSMS API."""
    api_key = getattr(settings, "SMS_API_KEY", "")
    sender = getattr(settings, "SMS_SENDER", "SvitPC")
    if not api_key:
        logger.info("SMS: SMS_API_KEY not configured, logging only. phone=%s template=%s", phone, template)
        return False

    try:
        body_tpl = f"sms/{template}.txt"
        text = render_to_string(body_tpl, ctx).strip()
    except Exception:
        text = str(ctx)[:160]

    import httpx
    try:
        resp = httpx.post(
            "https://api.turbosms.ua/message/send.json",
            json={
                "recipients": [phone],
                "sms": {
                    "sender": sender,
                    "text": text,
                },
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        data = resp.json()
        # TurboSMS returns {response_code: 0, ...} on success
        if data.get("response_code") == 0:
            return True
        logger.warning("TurboSMS error: %s", data)
        return False
    except Exception as exc:
        logger.error("SMS send error to %s: %s", phone, exc)
        return False


def _send_telegram(chat_id: str, template: str, ctx: dict) -> bool:
    """Send via Telegram bot."""
    import httpx

    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return False
    try:
        body_tpl = f"telegram/{template}.txt"
        text = render_to_string(body_tpl, ctx)
    except Exception:
        text = str(ctx)
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def _send_viber(chat_id: str, template: str, ctx: dict) -> bool:
    """Send via Viber Bot API."""
    import httpx
    from django.conf import settings

    token = getattr(settings, "VIBER_BOT_TOKEN", "")
    if not token:
        logger.info("Viber: VIBER_BOT_TOKEN not configured, skipping")
        return False

    try:
        body_tpl = f"viber/{template}.txt"
        text = render_to_string(body_tpl, ctx)
    except Exception:
        text = str(ctx)

    try:
        resp = httpx.post(
            "https://chatapi.viber.com/pa/send_message",
            headers={"X-Viber-Auth-Token": token},
            json={
                "receiver": chat_id,
                "min_api_version": 1,
                "type": "text",
                "text": text,
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("status") != 0:
            logger.warning("Viber send failed: %s", data.get("status_message"))
            return False
        return True
    except Exception as exc:
        logger.error("Viber send error: %s", exc)
        return False


def _send_push(user_pk: str | int, template: str, ctx: dict) -> bool:
    """Web-push via pywebpush to all subscriptions of a user.

    ctx keys: title, body, url, tag, icon (all optional).
    Stale subscriptions (410/404 from push service) are auto-deleted.
    """
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush not installed — push skipped")
        return False

    private_key = getattr(settings, "VAPID_PRIVATE_KEY", "")
    claims_email = getattr(settings, "VAPID_CLAIMS_EMAIL", "admin@svitpc.ua")
    if not private_key:
        return False

    from .models import PushSubscription

    subscriptions = list(PushSubscription.objects.filter(customer_id=user_pk))
    if not subscriptions:
        return False

    import json as _json

    payload = _json.dumps({
        "title": ctx.get("title", "СвітПК"),
        "body": ctx.get("body", ""),
        "url": ctx.get("url", "/"),
        "tag": ctx.get("tag", "svitpc-notification"),
        "icon": ctx.get("icon", "/static/images/icons/icon-192.png"),
    })

    stale_pks: list[int] = []
    sent = False
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": f"mailto:{claims_email}"},
            )
            sent = True
        except WebPushException as exc:
            response = getattr(exc, "response", None)
            if response is not None and response.status_code in (404, 410):
                stale_pks.append(sub.pk)
            else:
                logger.warning("WebPush error sub=%s: %s", sub.pk, exc)
        except Exception as exc:
            logger.warning("Push send error sub=%s: %s", sub.pk, exc)

    if stale_pks:
        PushSubscription.objects.filter(pk__in=stale_pks).delete()

    return sent
