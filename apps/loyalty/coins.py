"""Coin accrual, milestone rewards, and expiration."""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.loyalty.constants import (
    COUPON_VALIDITY_DAYS,
    EARN_TIERS,
    MILESTONES,
    MILESTONES_ASC,
    MIN_ORDER_FOR_COINS,
    COIN_LIFETIME_DAYS,
)
from apps.loyalty.models import BonusTransaction, Coupon


@dataclass(frozen=True)
class PendingCoinOrder:
    order_id: int
    coins: int


def coins_for_order_total(total: Decimal) -> int:
    """Return coins earned for a delivered order total (UAH)."""
    amount = total.quantize(Decimal("0.01"))
    if amount < MIN_ORDER_FOR_COINS:
        return 0
    for min_total, max_total, coins in EARN_TIERS:
        if amount < min_total:
            continue
        if max_total is not None and amount > max_total:
            continue
        return coins
    return 0


def order_total_for_coins(order) -> Decimal:
    """Product subtotal before coupons — basis for coin tiers."""
    return (order.total + order.discount + order.bonus_used).quantize(Decimal("0.01"))


def coins_for_order(order) -> int:
    """Coins this order will earn (or earned) based on its product subtotal."""
    return coins_for_order_total(order_total_for_coins(order))


def pending_coin_orders_for_customer(customer) -> list[PendingCoinOrder]:
    """Open orders that will earn coins once delivered."""
    from django.db.models import Exists, OuterRef

    from apps.orders.models import Order

    earn_exists = BonusTransaction.objects.filter(
        order=OuterRef("pk"),
        transaction_type=BonusTransaction.TYPE_EARN,
    )
    orders = (
        Order.objects.filter(customer=customer)
        .exclude(status__is_completed=True)
        .annotate(_has_earn=Exists(earn_exists))
        .filter(_has_earn=False)
        .order_by("-created_at")
    )
    pending: list[PendingCoinOrder] = []
    for order in orders:
        coins = coins_for_order(order)
        if coins > 0:
            pending.append(PendingCoinOrder(order_id=order.pk, coins=coins))
    return pending


def total_pending_coins(customer) -> int:
    return sum(item.coins for item in pending_coin_orders_for_customer(customer))


def _generate_coupon_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "COIN-" + "".join(secrets.choice(alphabet) for _ in range(8))


@dataclass(frozen=True)
class MilestoneProgress:
    current: int
    target: int
    reward_uah: Decimal
    remaining: int


def next_milestone_progress(balance: int) -> MilestoneProgress | None:
    """Next unreached milestone for UI progress bar."""
    for threshold, reward in MILESTONES_ASC:
        if balance < threshold:
            return MilestoneProgress(
                current=balance,
                target=threshold,
                reward_uah=reward,
                remaining=threshold - balance,
            )
    return None


def _create_coin_reward_coupon(customer, discount_uah: Decimal) -> Coupon:
    code = _generate_coupon_code()
    while Coupon.objects.filter(code=code).exists():
        code = _generate_coupon_code()
    now = timezone.now()
    return Coupon.objects.create(
        customer=customer,
        code=code,
        discount_type="fixed",
        discount_value=discount_uah,
        valid_from=now,
        valid_to=now + timedelta(days=COUPON_VALIDITY_DAYS),
        max_uses=1,
        is_active=True,
        source=Coupon.SOURCE_COIN_REWARD,
    )


@transaction.atomic
def process_milestone_rewards(customer) -> list[Coupon]:
    """Redeem coin milestones into personal fixed-amount coupons."""
    user_model = get_user_model()
    customer = user_model.objects.select_for_update().get(pk=customer.pk)
    issued: list[Coupon] = []

    balance = int(customer.bonus_balance)
    for threshold, reward_uah in MILESTONES:
        while balance >= threshold:
            coupon = _create_coin_reward_coupon(customer, reward_uah)
            balance -= threshold
            customer.bonus_balance = Decimal(balance)
            customer.save(update_fields=["bonus_balance"])
            BonusTransaction.objects.create(
                customer=customer,
                transaction_type=BonusTransaction.TYPE_REDEEM,
                amount=Decimal(threshold),
                balance_after=customer.bonus_balance,
                description=f"Обмін {threshold} монет на купон {reward_uah:.0f} ₴ ({coupon.code})",
            )
            issued.append(coupon)

    return issued


@transaction.atomic
def accrue_coins_for_order(order) -> BonusTransaction | None:
    """Credit coins after delivery; idempotent per order."""
    if not order.customer_id:
        return None
    if BonusTransaction.objects.filter(
        order=order,
        transaction_type=BonusTransaction.TYPE_EARN,
    ).exists():
        return None

    coins = coins_for_order_total(order_total_for_coins(order))
    if coins <= 0:
        return None

    user_model = get_user_model()
    customer = user_model.objects.select_for_update().get(pk=order.customer_id)
    expires_at = timezone.now() + timedelta(days=COIN_LIFETIME_DAYS)
    customer.bonus_balance += Decimal(coins)
    customer.save(update_fields=["bonus_balance"])
    tx = BonusTransaction.objects.create(
        customer=customer,
        order=order,
        transaction_type=BonusTransaction.TYPE_EARN,
        amount=Decimal(coins),
        balance_after=customer.bonus_balance,
        expires_at=expires_at,
        description=f"+{coins} монет за замовлення #{order.pk}",
    )
    process_milestone_rewards(customer)
    return tx


@transaction.atomic
def expire_customer_coins(customer) -> int:
    """Expire unprocessed earn batches past their lifetime."""
    user_model = get_user_model()
    customer = user_model.objects.select_for_update().get(pk=customer.pk)
    now = timezone.now()
    expired_total = 0

    earn_rows = (
        BonusTransaction.objects.select_for_update()
        .filter(
            customer=customer,
            transaction_type=BonusTransaction.TYPE_EARN,
            is_expired=False,
            expires_at__lt=now,
        )
        .order_by("expires_at", "pk")
    )
    for row in earn_rows:
        coins = int(row.amount)
        if coins <= 0:
            row.is_expired = True
            row.save(update_fields=["is_expired"])
            continue
        deduct = min(coins, int(customer.bonus_balance))
        if deduct <= 0:
            row.is_expired = True
            row.save(update_fields=["is_expired"])
            continue
        customer.bonus_balance -= Decimal(deduct)
        customer.save(update_fields=["bonus_balance"])
        BonusTransaction.objects.create(
            customer=customer,
            transaction_type=BonusTransaction.TYPE_EXPIRE,
            amount=Decimal(deduct),
            balance_after=customer.bonus_balance,
            description=f"Списано {deduct} монет — термін дії минув",
        )
        row.is_expired = True
        row.save(update_fields=["is_expired"])
        expired_total += deduct

    return expired_total
