"""Loyalty: coupon validation, checkout totals, coin balance adjustments."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.loyalty.constants import COUPON_MAX_ORDER_PERCENT
from apps.loyalty.models import BonusTransaction, Coupon


class LoyaltyError(Exception):
    """User-facing loyalty validation error."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def normalize_coupon_code(code: str) -> str:
    return code.strip().upper()


def validate_coupon(
    code: str,
    *,
    customer,
    subtotal: Decimal,
) -> Coupon:
    """Return a valid coupon or raise LoyaltyError."""
    normalized = normalize_coupon_code(code)
    if not normalized:
        raise LoyaltyError("Введіть промокод.")

    try:
        coupon = Coupon.objects.get(code__iexact=normalized)
    except Coupon.DoesNotExist:
        raise LoyaltyError("Промокод не знайдено.")

    if not coupon.is_active:
        raise LoyaltyError("Промокод неактивний.")

    now = timezone.now()
    if coupon.valid_from and now < coupon.valid_from:
        raise LoyaltyError("Промокод ще не дійсний.")
    if coupon.valid_to and now > coupon.valid_to:
        raise LoyaltyError("Термін дії промокоду закінчився.")

    if coupon.max_uses and coupon.used_count >= coupon.max_uses:
        raise LoyaltyError("Промокод уже використано максимальну кількість разів.")

    if subtotal < coupon.min_order_amount:
        raise LoyaltyError(
            f"Мінімальна сума замовлення для цього промокоду — {coupon.min_order_amount:.0f} ₴."
        )

    if coupon.customer_id:
        if not customer or not customer.is_authenticated:
            raise LoyaltyError("Цей промокод доступний лише зареєстрованим клієнтам.")
        if coupon.customer_id != customer.pk:
            raise LoyaltyError("Промокод призначений іншому клієнту.")

    return coupon


def calculate_coupon_discount(coupon: Coupon, subtotal: Decimal) -> Decimal:
    if subtotal <= 0:
        return Decimal("0")
    # Coerce: у щойно створеного (не перечитаного з БД) Coupon discount_value може бути int
    value = Decimal(str(coupon.discount_value))
    if coupon.discount_type == "percent":
        discount = (subtotal * value / Decimal("100")).quantize(Decimal("0.01"))
    else:
        discount = value.quantize(Decimal("0.01"))
    discount = min(discount, subtotal)
    if coupon.source == Coupon.SOURCE_COIN_REWARD:
        max_by_percent = (subtotal * COUPON_MAX_ORDER_PERCENT / Decimal("100")).quantize(Decimal("0.01"))
        discount = min(discount, max_by_percent)
    return discount


@dataclass(frozen=True)
class CheckoutLoyaltyTotals:
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    coupon: Coupon | None
    coupon_code: str


def resolve_checkout_loyalty(
    *,
    subtotal: Decimal,
    customer,
    coupon_code: str = "",
) -> CheckoutLoyaltyTotals:
    """Validate coupon and compute product totals for checkout."""
    discount = Decimal("0")
    coupon: Coupon | None = None
    code = normalize_coupon_code(coupon_code)

    if code:
        coupon = validate_coupon(code, customer=customer, subtotal=subtotal)
        discount = calculate_coupon_discount(coupon, subtotal)

    total = (subtotal - discount).quantize(Decimal("0.01"))
    if total < 0:
        total = Decimal("0")

    return CheckoutLoyaltyTotals(
        subtotal=subtotal,
        discount=discount,
        total=total,
        coupon=coupon,
        coupon_code=code,
    )


@transaction.atomic
def apply_loyalty_to_order(
    order,
    *,
    customer,
    coupon: Coupon | None,
) -> None:
    """Mark coupon as used after order placement."""
    if coupon:
        coupon = Coupon.objects.select_for_update().get(pk=coupon.pk)
        if coupon.max_uses and coupon.used_count >= coupon.max_uses:
            raise LoyaltyError("Промокод уже використано.")
        coupon.used_count += 1
        update_fields = ["used_count"]
        if coupon.max_uses and coupon.used_count >= coupon.max_uses:
            coupon.is_active = False
            update_fields.append("is_active")
        coupon.save(update_fields=update_fields)


@transaction.atomic
def apply_bonus_adjustment(customer, delta: Decimal, description: str = "") -> BonusTransaction:
    """Manual coin balance change from admin (TYPE_ADJUST audit record)."""
    user_model = get_user_model()
    customer = user_model.objects.select_for_update().get(pk=customer.pk)
    delta = delta.quantize(Decimal("0.01"))
    new_balance = (customer.bonus_balance + delta).quantize(Decimal("0.01"))
    if new_balance < 0:
        raise LoyaltyError("Баланс монет не може бути від'ємним.")
    customer.bonus_balance = new_balance
    customer.save(update_fields=["bonus_balance"])
    return BonusTransaction.objects.create(
        customer=customer,
        transaction_type=BonusTransaction.TYPE_ADJUST,
        amount=delta,
        balance_after=new_balance,
        description=description or "Коригування адміністратором",
    )
