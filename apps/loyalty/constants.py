"""SvitPC coin loyalty program constants."""

from __future__ import annotations

from decimal import Decimal

MIN_ORDER_FOR_COINS = Decimal("300")

# (min_total inclusive, max_total inclusive or None, coins)
EARN_TIERS: tuple[tuple[Decimal, Decimal | None, int], ...] = (
    (Decimal("300"), Decimal("2999.99"), 1),
    (Decimal("3000"), Decimal("4999.99"), 10),
    (Decimal("5000"), Decimal("9999.99"), 15),
    (Decimal("10000"), Decimal("19999.99"), 25),
    (Decimal("20000"), None, 50),
)

# Highest threshold first — used when redeeming milestones.
MILESTONES: tuple[tuple[int, Decimal], ...] = (
    (50, Decimal("700")),
    (25, Decimal("300")),
    (10, Decimal("100")),
)

# Ascending — used for progress UI.
MILESTONES_ASC: tuple[tuple[int, Decimal], ...] = (
    (10, Decimal("100")),
    (25, Decimal("300")),
    (50, Decimal("700")),
)

COIN_LIFETIME_DAYS = 183  # ~6 months
COUPON_MAX_ORDER_PERCENT = Decimal("20")
COUPON_VALIDITY_DAYS = 90
