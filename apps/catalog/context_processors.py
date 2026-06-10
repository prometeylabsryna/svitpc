"""Catalog template context."""

from __future__ import annotations

from django.http import HttpRequest

from .nav import get_top_categories


def catalog_nav(request: HttpRequest) -> dict:
    """Top categories with subcategories for header/footer navigation."""
    return {"top_categories": get_top_categories()}
