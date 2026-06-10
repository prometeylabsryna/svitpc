"""Catalog template tags."""

from __future__ import annotations

from django import template

from apps.catalog.category_icons import resolve_category_icon_id

register = template.Library()


@register.inclusion_tag("catalog/partials/category_nav_icon.html")
def category_nav_icon(category) -> dict:
    """Render inline SVG icon for a category (uploaded icon takes precedence in template)."""
    return {"icon_id": resolve_category_icon_id(category)}
