"""Catalog template tags."""

from __future__ import annotations

from django import template

from apps.catalog.category_icons import resolve_category_icon_id

register = template.Library()


@register.inclusion_tag("catalog/partials/category_nav_icon.html")
def category_nav_icon(category, icon_class: str = "site-nav__icon-svg") -> dict:
    """Render inline SVG icon for a category (uploaded icon takes precedence in template).

    ``icon_class`` lets callers size/style the SVG per context (sidebar nav vs
    subcategory cards) without duplicating the icon path data.
    """
    return {"icon_id": resolve_category_icon_id(category), "icon_class": icon_class}
