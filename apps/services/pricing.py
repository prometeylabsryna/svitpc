"""Format service price list rows for display."""

from __future__ import annotations

from decimal import Decimal

from django.utils.translation import gettext as _

from .models import PriceItem


def format_price_amount(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01"))
    if normalized == normalized.to_integral_value():
        amount = f"{int(normalized):,}".replace(",", "\u00a0")
    else:
        amount = f"{normalized:,.2f}".replace(",", "\u00a0")
    return f"{amount} ₴"


def format_price_item(price: PriceItem) -> str:
    if price.price_text.strip():
        return price.price_text.strip()

    price_from = price.price_from
    price_to = price.price_to

    if price_from is not None and price_to is not None:
        if price_from == price_to:
            return format_price_amount(price_from)
        return _("від %(from)s до %(to)s") % {
            "from": format_price_amount(price_from),
            "to": format_price_amount(price_to),
        }
    if price_from is not None:
        return _("від %(price)s") % {"price": format_price_amount(price_from)}
    if price_to is not None:
        return _("до %(price)s") % {"price": format_price_amount(price_to)}
    return ""
