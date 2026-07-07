"""Shared Django admin performance defaults."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest

# Pre-compute admin path prefix once at import time.
_ADMIN_PREFIX: str = "/" + getattr(settings, "ADMIN_URL", "admin/").strip("/") + "/"


def admin_is_changelist(request: HttpRequest) -> bool:
    match = getattr(request, "resolver_match", None)
    return bool(match and match.url_name and match.url_name.endswith("_changelist"))


def is_admin_request(request: HttpRequest) -> bool:
    """True for any request handled by the Django admin site."""
    return request.path.startswith(_ADMIN_PREFIX)


class OptimizedAdminMixin:
    """Fewer rows per page and skip expensive COUNT(*) on large tables."""

    list_per_page = 25
    show_full_result_count = False
