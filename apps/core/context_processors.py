"""Global template context processors."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest

from apps.core.models import SiteSettings
from apps.core.store import store_address, store_maps_embed_url, store_maps_url


def site_context(request: HttpRequest) -> dict:
    """Inject site-wide variables into every template."""
    site = SiteSettings.load()
    lang = request.LANGUAGE_CODE if hasattr(request, "LANGUAGE_CODE") else "uk"
    tagline = site.localized("tagline", lang=lang)
    return {
        "SITE_URL": settings.SITE_URL,
        "SITE_NAME": site.localized("name", lang=lang),
        "SITE_PHONE": site.phone,
        "SITE_VIBER_PHONE": site.effective_viber_phone(),
        "SITE_EMAIL": site.email,
        "SITE_ADDRESS": store_address(site),
        "SITE_MAPS_URL": store_maps_url(),
        "SITE_MAPS_EMBED_URL": store_maps_embed_url(),
        "SITE_TAGLINE": tagline,
        "SITE_FACEBOOK_URL": site.facebook_url,
        "SITE_INSTAGRAM_URL": site.instagram_url,
        "SITE_TELEGRAM_URL": site.telegram_url,
        "SITE_LEGAL_ENTITY": site.legal_entity,
        "SITE_LEGAL_NAME": site.legal_name,
        "SITE_TAX_ID": site.tax_id,
        "SITE_LEGAL_ADDRESS": site.legal_address,
        "SITE_HAS_LEGAL_INFO": site.has_legal_info(),
        "CURRENT_LANGUAGE": lang,
        "VAPID_PUBLIC_KEY": getattr(settings, "VAPID_PUBLIC_KEY", ""),
        "TELEGRAM_BOT_LINK": getattr(settings, "TELEGRAM_BOT_LINK", ""),
    }
