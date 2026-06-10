"""Review URL helpers."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest
from django.utils import translation

from apps.catalog.models import Product


def product_review_return_url(request: HttpRequest, product: Product) -> str:
    """Same-page return URL for the product reviews tab (path + #reviews hash)."""
    path = product.get_absolute_url()
    lang = getattr(request, "LANGUAGE_CODE", None) or translation.get_language()
    if lang and lang != settings.LANGUAGE_CODE:
        path = f"/{lang}{path}"
    return f"{path}#reviews"
