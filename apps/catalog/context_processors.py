"""Catalog template context."""

from __future__ import annotations

from django.http import HttpRequest

from apps.core.admin_mixins import is_admin_request

from .nav import get_top_categories


def catalog_nav(request: HttpRequest) -> dict:
    """Top categories with subcategories for header/footer navigation."""
    if is_admin_request(request):
        return {}
    return {"top_categories": get_top_categories()}
