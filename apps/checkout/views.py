"""Checkout wizard: step1 (delivery) → step2 (payment + loyalty) → confirm."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

from apps.analytics.ecommerce import order_purchase_payload
from apps.cart.cart import Cart
from apps.catalog.models import Product
from apps.core.svitik import cart_coin_hint, cart_coin_hint_message, cart_coin_hint_parts
from apps.loyalty.coins import coins_for_order_total, order_total_for_coins
from apps.loyalty.services import LoyaltyError, apply_loyalty_to_order, resolve_checkout_loyalty
from apps.orders.models import Order, OrderItem, OrderStatus
from apps.shipping.helpers import build_delivery_context, cart_weight_kg
from apps.shipping.validation import validate_checkout_step1

LOYALTY_SESSION_KEY = "checkout_loyalty"

_CONTACT_DEFAULTS: dict[str, str] = {
    "first_name": "",
    "last_name": "",
    "email": "",
    "phone": "",
}


def _customer_contact_prefill(user) -> dict[str, str]:
    """Profile defaults for checkout — only for regular shoppers, not staff accounts."""
    if not user.is_authenticated:
        return {}
    if user.is_staff or user.is_superuser:
        return {}
    data: dict[str, str] = {}
    if user.first_name:
        data["first_name"] = user.first_name
    if user.last_name:
        data["last_name"] = user.last_name
    if user.email:
        data["email"] = user.email
    if getattr(user, "phone", ""):
        data["phone"] = user.phone
    return data


def _checkout_step1_form_data(request: HttpRequest, posted: dict | None = None) -> dict:
    """Merge session, profile prefill, and defaults so templates never miss keys."""
    saved = posted if posted is not None else request.session.get("checkout_step1", {})
    prefill = _customer_contact_prefill(request.user)
    return {**_CONTACT_DEFAULTS, **prefill, **saved}


def _default_status() -> OrderStatus:
    return OrderStatus.objects.order_by("sort_order").first() or OrderStatus.objects.create(name="Нове", sort_order=0)


def _loyalty_from_session(request: HttpRequest) -> dict:
    return request.session.get(LOYALTY_SESSION_KEY, {})


def _save_loyalty_session(request: HttpRequest, data: dict) -> None:
    request.session[LOYALTY_SESSION_KEY] = data
    request.session.modified = True


def _clear_loyalty_session(request: HttpRequest) -> None:
    request.session.pop(LOYALTY_SESSION_KEY, None)


def _loyalty_context(request: HttpRequest, cart: Cart) -> dict:
    """Build loyalty totals for templates; on error clears invalid session data."""
    loyalty_data = _loyalty_from_session(request)
    coupon_code = loyalty_data.get("coupon_code", "")

    try:
        totals = resolve_checkout_loyalty(
            subtotal=cart.total,
            customer=request.user if request.user.is_authenticated else None,
            coupon_code=coupon_code,
        )
    except LoyaltyError as exc:
        _clear_loyalty_session(request)
        return {
            "loyalty_error": str(exc.message),
            "loyalty": None,
        }

    return {
        "loyalty": totals,
        "loyalty_error": None,
        "loyalty_session": loyalty_data,
    }


def _checkout_svitik_context(cart: Cart) -> dict:
    hint = cart_coin_hint(cart.total)
    return {
        "checkout_coin_hint": cart_coin_hint_message(hint),
        "checkout_coin_hint_parts": cart_coin_hint_parts(hint),
        "checkout_coin_coins": hint.current_coins or None,
    }


def checkout_step1_view(request: HttpRequest) -> HttpResponse:
    """Step 1: contact + delivery info."""
    cart = Cart(request)
    if not len(cart):
        return redirect("cart:detail")

    if request.method == "POST":
        step1 = request.POST.dict()
        errors = validate_checkout_step1(step1)
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(
                request,
                "checkout/step1.html",
                {
                    "cart": cart,
                    "form_data": _checkout_step1_form_data(request, step1),
                    **_checkout_svitik_context(cart),
                },
            )
        request.session["checkout_step1"] = step1
        return redirect("checkout:step2")

    return render(
        request,
        "checkout/step1.html",
        {
            "cart": cart,
            "form_data": _checkout_step1_form_data(request),
            **_checkout_svitik_context(cart),
        },
    )


def checkout_step2_view(request: HttpRequest) -> HttpResponse:
    """Step 2: payment + promo/bonus."""
    cart = Cart(request)
    if not len(cart):
        return redirect("cart:detail")
    step1 = request.session.get("checkout_step1", {})
    if not step1:
        return redirect("checkout:step1")

    loyalty_ctx = _loyalty_context(request, cart)
    delivery_ctx = {}
    loyalty = loyalty_ctx.get("loyalty")
    if loyalty:
        delivery_ctx = build_delivery_context(step1, cart, loyalty.total)

    if request.method == "POST":
        payment_method = request.POST.get("payment_method", "card")
        coupon_code = request.POST.get("coupon_code", "").strip()

        try:
            resolve_checkout_loyalty(
                subtotal=cart.total,
                customer=request.user if request.user.is_authenticated else None,
                coupon_code=coupon_code,
            )
            _save_loyalty_session(request, {"coupon_code": coupon_code})
            request.session["checkout_step2"] = {"payment_method": payment_method}
            return redirect("checkout:confirm")
        except LoyaltyError as exc:
            messages.error(request, exc.message)

    return render(
        request,
        "checkout/step2.html",
        {
            "cart": cart,
            "step1": step1,
            "payment_choices": Order.PAYMENT_CHOICES,
            **loyalty_ctx,
            **delivery_ctx,
            **_checkout_svitik_context(cart),
        },
    )


def checkout_confirm_view(request: HttpRequest) -> HttpResponse:
    cart = Cart(request)
    step1 = request.session.get("checkout_step1", {})
    step2 = request.session.get("checkout_step2", {})
    if not step1 or not step2 or not len(cart):
        return redirect("checkout:step1")

    loyalty_ctx = _loyalty_context(request, cart)
    loyalty = loyalty_ctx.get("loyalty")
    delivery_ctx = build_delivery_context(step1, cart, loyalty.total) if loyalty else {}

    if request.method == "POST":
        if loyalty is None:
            messages.error(request, _("Перевірте промокод та спробуйте знову."))
            return redirect("checkout:step2")

        from apps.shipping.services import calc_delivery_cost

        delivery_type = step1.get("delivery_type", "nova_poshta")
        delivery_cost = calc_delivery_cost(
            delivery_type=delivery_type,
            city_ref=step1.get("city_ref", ""),
            warehouse_ref=step1.get("warehouse_ref", ""),
            postcode=step1.get("postcode", ""),
            weight_kg=cart_weight_kg(cart),
            declared_value=Decimal(str(loyalty.subtotal)),
        )

        try:
            with transaction.atomic():
                order = Order.objects.create(
                    customer=request.user if request.user.is_authenticated else None,
                    status=_default_status(),
                    first_name=step1.get("first_name", ""),
                    last_name=step1.get("last_name", ""),
                    email=step1.get("email", ""),
                    phone=step1.get("phone", ""),
                    delivery_type=delivery_type,
                    city=step1.get("city", ""),
                    city_ref=step1.get("city_ref", ""),
                    warehouse=step1.get("warehouse", ""),
                    warehouse_ref=step1.get("warehouse_ref", ""),
                    postcode=step1.get("postcode", ""),
                    payment_method=step2.get("payment_method", "card"),
                    comment=step1.get("comment", ""),
                    total=loyalty.total,
                    discount=loyalty.discount,
                    delivery_cost=delivery_cost,
                    coupon=loyalty.coupon,
                )
                for item in cart:
                    OrderItem.objects.create(
                        order=order,
                        product_id=item["product_id"],
                        name=item["name"],
                        price=item["price"],
                        qty=item["qty"],
                    )

                if loyalty.coupon:
                    apply_loyalty_to_order(
                        order,
                        customer=request.user if request.user.is_authenticated else None,
                        coupon=loyalty.coupon,
                    )
        except LoyaltyError as exc:
            messages.error(request, exc.message)
            return redirect("checkout:step2")

        cart.clear()
        del request.session["checkout_step1"]
        del request.session["checkout_step2"]
        _clear_loyalty_session(request)

        if order.payment_method == Order.PAYMENT_CASH_ON_DELIVERY:
            return redirect("checkout:success", pk=order.pk)

        from django.urls import reverse

        return redirect(
            reverse("payments:initiate", kwargs={"order_id": order.pk}) + "?provider=liqpay"
        )

    return render(
        request,
        "checkout/confirm.html",
        {
            "cart": cart,
            "step1": step1,
            "step2": step2,
            **loyalty_ctx,
            **delivery_ctx,
            **_checkout_svitik_context(cart),
        },
    )




@csrf_exempt
def checkout_success_view(request: HttpRequest, pk: int) -> HttpResponse:
    # LiqPay redirects here via POST with data+signature after payment.
    # Process it so is_paid is updated even when server_url webhook is unreachable (e.g. localhost).
    if request.method == "POST" and request.POST.get("data") and request.POST.get("signature"):
        from apps.integrations.payments.liqpay import LiqPayProvider
        LiqPayProvider().handle_webhook(request.POST)

    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=pk)
    order_coins = coins_for_order_total(order_total_for_coins(order))
    return render(
        request,
        "checkout/success.html",
        {
            "order": order,
            "ecommerce_purchase": order_purchase_payload(order),
            "order_coins": order_coins,
        },
    )


def one_click_view(request: HttpRequest, product_id: int) -> HttpResponse:
    """HTMX partial — 1-Click buy form."""
    from apps.notifications.phone import InvalidPhoneError, clean_ua_phone_for_storage

    product = get_object_or_404(Product, pk=product_id, is_visible=True)
    ctx: dict = {
        "product": product,
        "name_error": "",
        "phone_error": "",
        "posted_name": "",
        "posted_phone": "",
    }
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        phone_raw = request.POST.get("phone", "").strip()
        ctx["posted_name"] = name
        ctx["posted_phone"] = phone_raw

        if not name:
            ctx["name_error"] = str(_("Вкажіть ім'я."))

        phone = ""
        try:
            phone = clean_ua_phone_for_storage(phone_raw, required=True)
        except InvalidPhoneError:
            ctx["phone_error"] = str(_("Введіть коректний номер телефону (+380…)."))

        if name and phone:
            order = Order.objects.create(
                customer=request.user if request.user.is_authenticated else None,
                status=_default_status(),
                first_name=name,
                last_name="",
                email="",
                phone=phone,
                delivery_type="nova_poshta",
                payment_method="cod",
                total=product.price,
                comment=_("Замовлення в 1 клік"),
            )
            OrderItem.objects.create(order=order, product=product, name=product.name, price=product.price, qty=1)
            order = Order.objects.prefetch_related("items").get(pk=order.pk)
            return render(
                request,
                "checkout/one_click_success.html",
                {
                    "order": order,
                    "product": product,
                    "ecommerce_purchase": order_purchase_payload(order),
                },
            )
        return render(request, "checkout/one_click_form.html", ctx)
    return render(request, "checkout/one_click_form.html", ctx)
