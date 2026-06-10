"""Access decorators for service staff views."""

from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

F = TypeVar("F", bound=Callable[..., HttpResponse])


def staff_service_required(view_func: F) -> F:
    """Require authenticated staff for warranty / serial management UI."""

    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            return render(
                request,
                "services/warranty_forbidden.html",
                status=403,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped  # type: ignore[return-value]
