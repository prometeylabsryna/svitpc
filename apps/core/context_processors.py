"""Global template context processors."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest


def site_context(request: HttpRequest) -> dict:
    """Inject site-wide variables into every template."""
    return {
        "SITE_URL": settings.SITE_URL,
        "SITE_NAME": "СвітПК",
        "SITE_PHONE": "+38 (044) 000-00-00",
        "SITE_EMAIL": "info@svitpc.ua",
        "CURRENT_LANGUAGE": request.LANGUAGE_CODE if hasattr(request, "LANGUAGE_CODE") else "uk",
        "VAPID_PUBLIC_KEY": getattr(settings, "VAPID_PUBLIC_KEY", ""),
        "TELEGRAM_BOT_LINK": getattr(settings, "TELEGRAM_BOT_LINK", ""),
    }
