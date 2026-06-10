"""Separate Django sessions for admin and the public storefront."""

from __future__ import annotations

import time
from importlib import import_module

from django.conf import settings
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.exceptions import SessionInterrupted
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpRequest, HttpResponse
from django.utils.cache import patch_vary_headers
from django.utils.http import http_date


def is_admin_request(request: HttpRequest) -> bool:
    """True when the URL targets Django admin (with optional language prefix)."""
    admin_slug = settings.ADMIN_URL.strip("/")
    path_parts = [part for part in request.path_info.strip("/").split("/") if part]
    if not path_parts:
        return False

    lang_codes = {code for code, _ in settings.LANGUAGES}
    if path_parts[0] in lang_codes:
        return len(path_parts) > 1 and path_parts[1] == admin_slug
    return path_parts[0] == admin_slug


def session_cookie_name(request: HttpRequest) -> str:
    if is_admin_request(request):
        return settings.ADMIN_SESSION_COOKIE_NAME
    return settings.SESSION_COOKIE_NAME


class SplitSessionMiddleware(SessionMiddleware):
    """Use a dedicated session cookie for admin so staff login does not log in shoppers."""

    def process_request(self, request: HttpRequest) -> None:
        cookie_name = session_cookie_name(request)
        session_key = request.COOKIES.get(cookie_name)
        request.session = self.SessionStore(session_key)
        request._session_cookie_name = cookie_name

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        cookie_name = getattr(request, "_session_cookie_name", settings.SESSION_COOKIE_NAME)
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            return response

        if cookie_name in request.COOKIES and empty:
            response.delete_cookie(
                cookie_name,
                path=settings.SESSION_COOKIE_PATH,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
            patch_vary_headers(response, ("Cookie",))
        else:
            if accessed:
                patch_vary_headers(response, ("Cookie",))
            if (modified or settings.SESSION_SAVE_EVERY_REQUEST) and not empty:
                if request.session.get_expire_at_browser_close():
                    max_age = None
                    expires = None
                else:
                    max_age = request.session.get_expiry_age()
                    expires_time = time.time() + max_age
                    expires = http_date(expires_time)
                if response.status_code < 500:
                    try:
                        request.session.save()
                    except UpdateError as exc:
                        raise SessionInterrupted(
                            "The request's session was deleted before the "
                            "request completed. The user may have logged "
                            "out in a concurrent request, for example."
                        ) from exc
                    response.set_cookie(
                        cookie_name,
                        request.session.session_key,
                        max_age=max_age,
                        expires=expires,
                        domain=settings.SESSION_COOKIE_DOMAIN,
                        path=settings.SESSION_COOKIE_PATH,
                        secure=settings.SESSION_COOKIE_SECURE or None,
                        httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                        samesite=settings.SESSION_COOKIE_SAMESITE,
                    )
        return response
