"""Log i18n state when user follows account link from wishlist (session ced943)."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from apps.core.debug_i18n_log import write_debug_log

_WATCH_PREFIXES = ("/wishlist", "/en/wishlist", "/account", "/en/account")


class DebugI18nMiddleware(MiddlewareMixin):
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        path = request.path_info
        if not any(path.startswith(p) for p in _WATCH_PREFIXES):
            return response
        location_header = response.get("Location", "")
        write_debug_log(
            hypothesis_id="D",
            location="middleware_debug_i18n.process_response",
            message="response for wishlist/account path",
            data={
                "path": path,
                "status": response.status_code,
                "location": location_header,
                "language_code": getattr(request, "LANGUAGE_CODE", None),
            },
        )
        return response
