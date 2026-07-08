"""Shared Django admin performance defaults."""

from __future__ import annotations

from django.http import HttpRequest

from apps.core.session_middleware import is_admin_request  # noqa: F401
# is_admin_request реекспортовано з session_middleware — єдина i18n-aware
# реалізація (враховує /en/admin/). Раніше тут була копія лише для /admin/,
# через що context processors не пропускались на англомовній адмінці.


def admin_is_changelist(request: HttpRequest) -> bool:
    match = getattr(request, "resolver_match", None)
    return bool(match and match.url_name and match.url_name.endswith("_changelist"))


class OptimizedAdminMixin:
    """Fewer rows per page and skip expensive COUNT(*) on large tables."""

    list_per_page = 25
    show_full_result_count = False
