"""Спільні HTMX-хелпери."""

from __future__ import annotations

import json

from django.http import HttpResponse


def hx_trigger(response: HttpResponse, payload: dict) -> HttpResponse:
    """Виставити HX-Trigger з ASCII-safe JSON.

    ensure_ascii=True обов'язково: кирилиця в HTTP-заголовку RFC 2047-кодується
    Django і ламає JSON.parse на боці htmx (див. django_debug ERR-36).
    """
    response["HX-Trigger"] = json.dumps(payload, ensure_ascii=True)
    return response
