"""Custom template tags and filters for SvitPC."""

from __future__ import annotations

import re

from django import template

from apps.core.text import unescape_legacy_html
from apps.core.utils import ideal_cols

register = template.Library()

_CLASS_MAP = {1: "grid-cols-1", 2: "grid-cols-2", 3: "grid-cols-3", 4: "grid-cols-4"}


@register.filter(name="grid_cols_class")
def grid_cols_class(count: int, max_cols: int = 3) -> str:
    """Return a CSS class for the card grid (card_skill algorithm)."""
    cols = ideal_cols(int(count), int(max_cols))
    return _CLASS_MAP.get(cols, "grid-cols-3")


@register.filter(name="display_text")
def display_text(value: object) -> str:
    """Show catalog text without OpenCart HTML entities (``&#039;`` → ``'``)."""
    return unescape_legacy_html(str(value) if value is not None else "")


@register.filter(name="localized")
def localized(obj: object, field: str) -> str:
    """Bilingual DB field: ``name`` / ``name_en`` or modeltranslation accessors."""
    from apps.core.i18n import localized_field

    return localized_field(obj, field)


@register.filter(name="currency")
def currency(value: object) -> str:
    """Format as Ukrainian hryvnia."""
    try:
        return f"{float(value):,.0f} ₴".replace(",", "\u00a0")
    except (TypeError, ValueError):
        return str(value)


@register.simple_tag
def active_if(request, *urls: str) -> str:
    """Return 'is-active' CSS class if current URL matches any of the given named URLs."""
    from django.urls import reverse

    for url_name in urls:
        try:
            if request.path.startswith(reverse(url_name)):
                return "is-active"
        except Exception:
            pass
    return ""


@register.inclusion_tag("seo/jsonld_breadcrumbs.html")
def breadcrumbs(*items: tuple) -> dict:
    """Render breadcrumb JSON-LD + HTML. items = [(name, url), ...]"""
    return {"breadcrumbs": items}


@register.filter
def multiply(value: object, arg: object) -> float:
    """Multiply two values."""
    try:
        return float(value) * float(arg)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


@register.filter
def subtract(value: object, arg: object) -> float:
    """Subtract arg from value."""
    try:
        return float(value) - float(arg)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


@register.inclusion_tag("analytics/fb_pixel.html", takes_context=True)
def fb_pixel(context) -> dict:
    """Render Facebook/Meta Pixel noscript + meta tag (no inline scripts)."""
    from django.conf import settings
    pixel_id = getattr(settings, "FACEBOOK_PIXEL_ID", "")
    return {"FACEBOOK_PIXEL_ID": pixel_id}


@register.filter
def discount_percent(price: object, old_price: object) -> int:
    """Calculate discount percentage."""
    try:
        p = float(price)
        op = float(old_price)
        if op > 0:
            return round((op - p) / op * 100)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return 0


@register.filter(name="phone_digits")
def phone_digits(value: object) -> str:
    """Strip non-digits from a phone string for messenger deep links."""
    return re.sub(r"\D", "", str(value or ""))


def _messenger_phone_digits(value: object) -> str:
    digits = phone_digits(value)
    if len(digits) == 10 and digits.startswith("0"):
        return f"38{digits}"
    return digits


@register.simple_tag
def svitik_mascot(variant: str = "tip", mascot: str = "") -> str:
    """Static URL for a Pan Svitik mascot pose (WebP)."""
    from django.templatetags.static import static

    from apps.core.svitik import SVITIK_ASSET_VERSION, svitik_mascot_file

    filename = svitik_mascot_file(variant=variant, mascot=mascot or None)
    return f"{static(f'images/{filename}')}?v={SVITIK_ASSET_VERSION}"


@register.simple_tag
def svitik_mascot_png(variant: str = "tip", mascot: str = "") -> str:
    """PNG fallback URL for a Pan Svitik mascot pose."""
    from django.templatetags.static import static

    from apps.core.svitik import SVITIK_ASSET_VERSION, svitik_mascot_file, svitik_mascot_png_name

    filename = svitik_mascot_png_name(svitik_mascot_file(variant=variant, mascot=mascot or None))
    return f"{static(f'images/{filename}')}?v={SVITIK_ASSET_VERSION}"


@register.simple_tag
def svitik_mascot_sm(variant: str = "tip", mascot: str = "") -> str:
    """Mobile-sized WebP mascot (smaller file for narrow viewports)."""
    from django.templatetags.static import static

    from apps.core.svitik import SVITIK_ASSET_VERSION, svitik_mascot_file, svitik_mascot_sm_name

    filename = svitik_mascot_sm_name(svitik_mascot_file(variant=variant, mascot=mascot or None))
    return f"{static(f'images/{filename}')}?v={SVITIK_ASSET_VERSION}"


@register.simple_tag
def svitik_mascot_sm_png(variant: str = "tip", mascot: str = "") -> str:
    """PNG fallback for mobile-sized mascot."""
    from django.templatetags.static import static

    from apps.core.svitik import SVITIK_ASSET_VERSION, svitik_mascot_file, svitik_mascot_sm_name
    from apps.core.svitik import svitik_mascot_png_name

    webp = svitik_mascot_sm_name(svitik_mascot_file(variant=variant, mascot=mascot or None))
    filename = svitik_mascot_png_name(webp)
    return f"{static(f'images/{filename}')}?v={SVITIK_ASSET_VERSION}"


@register.simple_tag
def svitik_mascot_intrinsic(variant: str = "tip", mascot: str = "") -> dict[str, int]:
    """Width/height for layout hints (mobile sm asset when available)."""
    from apps.core.svitik import svitik_mascot_file, svitik_mascot_sm_dims

    filename = svitik_mascot_file(variant=variant, mascot=mascot or None)
    width, height = svitik_mascot_sm_dims(filename) or (0, 0)
    return {"width": width, "height": height}


@register.filter(name="viber_chat_url")
def viber_chat_url(value: object) -> str:
    """Build a Viber deep link from a phone string."""
    digits = _messenger_phone_digits(value)
    if not digits:
        return ""
    return f"viber://chat?number=%2B{digits}"
