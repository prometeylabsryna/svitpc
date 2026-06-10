"""Business logic for info pages."""

from __future__ import annotations

import logging

from django.conf import settings

from apps.core.models import SiteSettings
from apps.notifications.service import send_notification

from .models import ReturnRequest

logger = logging.getLogger(__name__)


def notify_return_request(claim: ReturnRequest) -> None:
    """Email store managers about a new return/exchange request."""
    site = SiteSettings.load()
    recipient = site.email or settings.DEFAULT_FROM_EMAIL
    ctx = {
        "claim": claim,
        "site_name": site.name,
        "site_phone": site.phone,
        "site_url": getattr(settings, "SITE_URL", "").rstrip("/"),
    }
    try:
        send_notification("email", recipient, "return_request", ctx)
    except Exception:
        logger.exception("Failed to notify about return request pk=%s", claim.pk)
