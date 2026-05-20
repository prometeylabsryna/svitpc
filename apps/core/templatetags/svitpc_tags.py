"""Custom template tags and filters for SvitPC."""

from __future__ import annotations

from django import template

from apps.core.utils import ideal_cols

register = template.Library()

_CLASS_MAP = {1: "grid-cols-1", 2: "grid-cols-2", 3: "grid-cols-3", 4: "grid-cols-4"}


@register.filter(name="grid_cols_class")
def grid_cols_class(count: int, max_cols: int = 3) -> str:
    """Return a CSS class for the card grid (card_skill algorithm)."""
    cols = ideal_cols(int(count), int(max_cols))
    return _CLASS_MAP.get(cols, "grid-cols-3")


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
