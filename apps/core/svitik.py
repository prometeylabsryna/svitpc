"""Pan Svitik — mascot hints for cart coins and product advice."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.utils.translation import gettext as _

from apps.loyalty.coins import coins_for_order_total
from apps.loyalty.constants import EARN_TIERS, MIN_ORDER_FOR_COINS

# Bump when mascot PNGs change (cache-bust static URLs).
SVITIK_ASSET_VERSION = "3"

# HQ poses from brand kit. Keys without a dedicated render reuse the closest pose.
SVITIK_MASCOTS: dict[str, str] = {
    "guide": "pan-svitik-tech.png",
    "welcome": "pan-svitik-choice.png",
    "cart": "pan-svitik-coins.png",
    "choice": "pan-svitik-choice.png",
    "search": "pan-svitik-search.png",
    "tech": "pan-svitik-tech.png",
    "coins": "pan-svitik-coins.png",
    "progress": "pan-svitik-celebrate.png",
    "celebrate": "pan-svitik-celebrate.png",
}

# Intrinsic pixel size of processed PNGs (width, height).
SVITIK_MASCOT_DIMS: dict[str, tuple[int, int]] = {
    "pan-svitik-choice.png": (712, 855),
    "pan-svitik-coins.png": (594, 912),
    "pan-svitik-search.png": (604, 862),
    "pan-svitik-tech.png": (709, 915),
    "pan-svitik-celebrate.png": (787, 872),
}

VARIANT_MASCOT: dict[str, str] = {
    "welcome": "welcome",
    "cart": "cart",
    "choice": "choice",
    "success": "celebrate",
    "checkout": "progress",
    "tip": "tech",
    "search": "search",
    "coins": "coins",
    "guide": "guide",
    "progress": "progress",
    "celebrate": "celebrate",
    "tech": "tech",
}


def svitik_mascot_file(*, variant: str = "tip", mascot: str | None = None) -> str:
    """Resolve mascot static filename for a UI variant or explicit mascot key."""
    key = mascot or VARIANT_MASCOT.get(variant, "guide")
    return SVITIK_MASCOTS.get(key, SVITIK_MASCOTS["guide"])


def svitik_mascot_dims(filename: str) -> tuple[int, int] | None:
    return SVITIK_MASCOT_DIMS.get(filename)


@dataclass(frozen=True)
class CartCoinHint:
    cart_total: Decimal
    current_coins: int
    next_coins: int | None
    remaining_uah: Decimal | None


@dataclass(frozen=True)
class CartCoinHintParts:
    """Structured cart coin hint for rich template rendering."""

    kind: str  # below_min | next_tier | earned
    total: str | None = None
    remaining: str | None = None
    coins: int | None = None
    next_coins: int | None = None


def cart_coin_hint(total: Decimal) -> CartCoinHint:
    """How many coins the cart earns now and what the next tier offers."""
    amount = total.quantize(Decimal("0.01"))
    current = coins_for_order_total(amount)
    next_coins: int | None = None
    remaining: Decimal | None = None

    for min_total, _max_total, coins in EARN_TIERS:
        if coins <= current:
            continue
        if amount < min_total:
            next_coins = coins
            remaining = (min_total - amount).quantize(Decimal("0.01"))
            break

    return CartCoinHint(
        cart_total=amount,
        current_coins=current,
        next_coins=next_coins,
        remaining_uah=remaining,
    )


def format_uah(amount: Decimal) -> str:
    return f"{float(amount):,.0f} ₴".replace(",", "\u00a0")


def cart_coin_hint_parts(hint: CartCoinHint) -> CartCoinHintParts | None:
    """Structured hint data for cart banner templates."""
    if hint.cart_total <= 0:
        return None

    if hint.current_coins == 0 and hint.remaining_uah is not None:
        return CartCoinHintParts(
            kind="below_min",
            remaining=format_uah(hint.remaining_uah),
        )

    if hint.next_coins is not None and hint.remaining_uah is not None:
        return CartCoinHintParts(
            kind="next_tier",
            total=format_uah(hint.cart_total),
            remaining=format_uah(hint.remaining_uah),
            coins=hint.current_coins,
            next_coins=hint.next_coins,
        )

    if hint.current_coins > 0:
        return CartCoinHintParts(
            kind="earned",
            coins=hint.current_coins,
        )

    return None


def cart_coin_hint_message(hint: CartCoinHint) -> str | None:
    """User-facing hint text; None when there is nothing useful to say."""
    if hint.cart_total <= 0:
        return None

    if hint.current_coins == 0 and hint.remaining_uah is not None:
        return _(
            "Додайте товарів ще на %(remaining)s, щоб отримати перші бонусні монети СвітПК!"
        ) % {"remaining": format_uah(hint.remaining_uah)}

    if hint.next_coins is not None and hint.remaining_uah is not None:
        if hint.current_coins > 0:
            return _(
                "У кошику товари на %(total)s. Після доставки ви отримаєте "
                "%(current)d бонусних монет. Додайте ще на %(remaining)s — і буде %(next)d."
            ) % {
                "total": format_uah(hint.cart_total),
                "current": hint.current_coins,
                "remaining": format_uah(hint.remaining_uah),
                "next": hint.next_coins,
            }
        return _(
            "У кошику товари на %(total)s. Додайте ще на %(remaining)s і отримаєте "
            "%(coins)d бонусних монет."
        ) % {
            "total": format_uah(hint.cart_total),
            "remaining": format_uah(hint.remaining_uah),
            "coins": hint.next_coins,
        }

    if hint.current_coins > 0:
        return _(
            "Чудово! Після доставки цього замовлення ви отримаєте %(coins)d бонусних монет СвітПК."
        ) % {"coins": hint.current_coins}

    return None


def cart_coin_hint_payload(hint: CartCoinHint) -> dict | None:
    """HX-Trigger / JS payload for a floating Svitik popup."""
    message = cart_coin_hint_message(hint)
    if not message:
        return None
    payload: dict = {
        "message": message,
        "variant": "cart",
        "mascot": svitik_mascot_file(variant="cart"),
    }
    if hint.current_coins > 0:
        payload["coins"] = hint.current_coins
    return payload


def svitik_event(
    message: str,
    *,
    variant: str = "tip",
    title: str = "",
    coins: int | None = None,
    mascot: str | None = None,
) -> dict:
    """Build an HX-Trigger ``svitik`` event payload."""
    payload: dict = {
        "message": message,
        "variant": variant,
        "mascot": svitik_mascot_file(variant=variant, mascot=mascot),
    }
    if title:
        payload["title"] = title
    if coins is not None:
        payload["coins"] = coins
    return payload


def product_purchase_tip(product) -> str | None:
    """Category-based cross-sell advice for product detail pages."""
    keywords: tuple[tuple[tuple[str, ...], str], ...] = (
        (
            ("noutbuk", "notebook", "laptop", "ноут"),
            _(
                "Порада від Пана Світика: часто купують разом із ноутбуком — "
                "миша, сумка, килимок, навушники."
            ),
        ),
        (
            ("kompyuter", "desktop", "pc", "комп"),
            _(
                "Порада від Пана Світика: до комп'ютера часто додають монітор, "
                "клавіатуру та мишу."
            ),
        ),
        (
            ("monitor", "монітор"),
            _(
                "Порада від Пана Світика: до монітора варто підібрати HDMI-кабель "
                "та кронштейн для зручного розміщення."
            ),
        ),
        (
            ("printer", "druk", "принтер"),
            _(
                "Порада від Пана Світика: не забудьте про папір та картриджі — "
                "їх часто беруть разом із принтером."
            ),
        ),
        (
            ("smartfon", "phone", "телефон"),
            _(
                "Порада від Пана Світика: до смартфона зазвичай додають чохол, "
                "захисне скло та зарядний пристрій."
            ),
        ),
    )

    haystack = " ".join(
        f"{cat.slug} {getattr(cat, 'name', '')}".lower()
        for cat in product.categories.all()
    )
    for keys, tip in keywords:
        if any(key in haystack for key in keys):
            return tip
    return None


def min_order_coin_gap(total: Decimal) -> Decimal | None:
    """Amount still needed before the cart qualifies for any coins."""
    amount = total.quantize(Decimal("0.01"))
    if amount >= MIN_ORDER_FOR_COINS:
        return None
    return (MIN_ORDER_FOR_COINS - amount).quantize(Decimal("0.01"))
