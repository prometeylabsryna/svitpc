"""Template tags for analytics / ecommerce meta payloads."""

from __future__ import annotations

from django import template

from apps.analytics.ecommerce import ecommerce_json as _ecommerce_json

register = template.Library()


@register.filter(name="ecommerce_json")
def ecommerce_json_filter(data: dict) -> str:
    return _ecommerce_json(data)
