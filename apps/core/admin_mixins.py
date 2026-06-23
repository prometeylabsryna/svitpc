"""Shared Django admin performance defaults."""

from __future__ import annotations

from django.http import HttpRequest


def admin_is_changelist(request: HttpRequest) -> bool:
    match = getattr(request, "resolver_match", None)
    return bool(match and match.url_name and match.url_name.endswith("_changelist"))


class OptimizedAdminMixin:
    """Fewer rows per page and skip expensive COUNT(*) on large tables."""

    list_per_page = 25
    show_full_result_count = False
