"""Temporary debug logging for i18n navigation (session ced943)."""

from __future__ import annotations

import json
import time
from typing import Any

from django.conf import settings
from django.urls import reverse
from django.utils import translation

LOG_PATH = "/Users/olegbonislavskyi/Sites/SvitPC/.cursor/debug-ced943.log"
SESSION_ID = "ced943"


def write_debug_log(
    *,
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict[str, Any],
    run_id: str = "pre-fix",
) -> None:
    # #region agent log
    entry = {
        "sessionId": SESSION_ID,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
    # #endregion


def log_request_i18n(request: Any, *, view: str) -> None:
    """Log language state and reversed URLs for wishlist/account flows."""
    cookie_name = getattr(settings, "LANGUAGE_COOKIE_NAME", "django_language")
    data = {
        "view": view,
        "path": request.path_info,
        "full_path": request.get_full_path(),
        "language_code": getattr(request, "LANGUAGE_CODE", None),
        "get_language": translation.get_language(),
        "language_cookie": request.COOKIES.get(cookie_name),
        "user_authenticated": getattr(request.user, "is_authenticated", False),
        "dashboard_url": reverse("customers:dashboard"),
        "wishlist_url": reverse("wishlist:page"),
        "login_url_setting": settings.LOGIN_URL,
    }
    write_debug_log(
        hypothesis_id="A",
        location=f"debug_i18n_log.log_request_i18n:{view}",
        message="i18n state on page render",
        data=data,
    )
