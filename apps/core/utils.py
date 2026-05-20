"""Shared utilities for the SvitPC project."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse


def axes_lockout(request: HttpRequest, credentials: dict | None = None) -> HttpResponse:
    """Custom lockout response for django-axes."""
    from django.shortcuts import render

    return render(request, "core/lockout.html", status=403)


def ideal_cols(count: int, max_cols: int = 3) -> int:
    """Return optimal column count so all grid rows are equal (card_skill algorithm)."""
    n = max(1, count)
    if n <= max_cols:
        return n
    for c in range(max_cols, 1, -1):
        if n % c == 0:
            return c
    return max_cols
