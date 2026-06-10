"""Safe post-login / post-registration redirect helpers."""

from __future__ import annotations

from urllib.parse import urlparse

from django.http import HttpRequest
from django.utils.encoding import iri_to_uri
from django.utils.http import url_has_allowed_host_and_scheme


def safe_next_url(request: HttpRequest, candidate: str | None, *, fallback: str) -> str:
    """Return *candidate* when it is a same-host path or URL, else *fallback*."""
    if not candidate:
        return fallback
    if not url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return fallback
    parsed = urlparse(candidate)
    if parsed.netloc:
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        if parsed.fragment:
            path = f"{path}#{parsed.fragment}"
        return path
    return candidate


def htmx_redirect_url(url: str) -> str:
    """ASCII-safe URL for the HX-Redirect header.

    Django RFC 2047–encodes non-ASCII header values; HTMX passes the encoded
    string to ``location.href`` and navigation fails.
    """
    return iri_to_uri(url)
