"""Retail price guards — never sell below cost + configured markup."""

from __future__ import annotations

from decimal import Decimal

from .services import apply_markup


def minimum_retail_price(
    purchase_price: Decimal | None,
    brand_id: int | None,
    category_ids: list[int] | None,
) -> Decimal | None:
    """Lowest allowed shelf price for a purchase cost (cost + MarkupRule)."""
    if purchase_price is None or purchase_price <= 0:
        return None
    return apply_markup(purchase_price, brand_id, category_ids or [])


def enforce_retail_price(
    retail: Decimal,
    purchase_price: Decimal | None,
    *,
    brand_id: int | None = None,
    category_ids: list[int] | None = None,
) -> Decimal:
    """Bump retail up to minimum when sync/import/admin left it below cost."""
    minimum = minimum_retail_price(purchase_price, brand_id, category_ids)
    if minimum is None:
        return retail
    return max(retail, minimum)


def reconcile_old_price(retail: Decimal, old_price: Decimal | None) -> Decimal | None:
    """Drop stale crossed-out price when it is no longer above retail."""
    if old_price is None:
        return None
    if old_price <= retail:
        return None
    return old_price
