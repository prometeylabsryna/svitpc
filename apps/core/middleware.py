"""Core middleware: legacy OpenCart URL redirects."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse, HttpResponsePermanentRedirect
from django.utils.deprecation import MiddlewareMixin

from apps.core.redirect_cache import get_redirect_target


class RedirectMiddleware(MiddlewareMixin):
    """Handle 301 redirects stored in catalog.Redirect model."""

    def process_request(self, request: HttpRequest) -> HttpResponse | None:
        new_path = get_redirect_target(request.path_info)
        if new_path:
            return HttpResponsePermanentRedirect(new_path)
        return None
