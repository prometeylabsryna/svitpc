"""Core middleware: legacy OpenCart URL redirects."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse, HttpResponsePermanentRedirect
from django.utils.deprecation import MiddlewareMixin


class RedirectMiddleware(MiddlewareMixin):
    """Handle 301 redirects stored in catalog.Redirect model."""

    def process_request(self, request: HttpRequest) -> HttpResponse | None:
        path = request.path_info
        try:
            from apps.catalog.models import Redirect

            redirect_obj = Redirect.objects.filter(old_path=path, is_active=True).first()
            if redirect_obj:
                return HttpResponsePermanentRedirect(redirect_obj.new_path)
        except Exception:
            pass
        return None
