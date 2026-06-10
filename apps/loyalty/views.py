from django.contrib.auth.decorators import login_required
from django.db.models import F, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.loyalty.coins import next_milestone_progress, pending_coin_orders_for_customer, total_pending_coins
from apps.loyalty.constants import EARN_TIERS, MILESTONES_ASC, MIN_ORDER_FOR_COINS
from apps.loyalty.models import BonusTransaction, Coupon


@login_required
def bonus_view(request: HttpRequest) -> HttpResponse:
    balance = int(request.user.bonus_balance)
    pending_orders = pending_coin_orders_for_customer(request.user)
    pending_coins = total_pending_coins(request.user)
    transactions = BonusTransaction.objects.filter(customer=request.user).select_related("order")[:50]
    progress = next_milestone_progress(balance + pending_coins)
    active_coupons = (
        Coupon.objects.filter(
            customer=request.user,
            is_active=True,
            source=Coupon.SOURCE_COIN_REWARD,
        )
        .filter(Q(max_uses=0) | Q(used_count__lt=F("max_uses")))
        .order_by("-valid_from")[:10]
    )
    return render(
        request,
        "loyalty/bonus.html",
        {
            "transactions": transactions,
            "coin_balance": balance,
            "pending_coins": pending_coins,
            "pending_orders": pending_orders,
            "progress": progress,
            "earn_tiers": EARN_TIERS,
            "milestones": MILESTONES_ASC,
            "min_order_for_coins": MIN_ORDER_FOR_COINS,
            "active_coupons": active_coupons,
        },
    )
