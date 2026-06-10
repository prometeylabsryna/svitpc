"""Customer display helpers."""

from __future__ import annotations

from django.utils.translation import gettext as _

from .models import Customer


def customer_display_name(user: Customer) -> str:
    name = (user.first_name or user.get_short_name() or "").strip()
    if not name:
        name = user.email.split("@", 1)[0]
    return name


def customer_welcome_message(user: Customer) -> str:
    return str(_("Вітаю, %(name)s!") % {"name": customer_display_name(user)})
