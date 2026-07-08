import json

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.analytics.ecommerce import cart_action_payload
from apps.core.svitik import (
    cart_coin_hint,
    cart_coin_hint_parts,
    cart_coin_hint_payload,
    svitik_event,
)

from .cart import Cart


def _cart_context(cart: Cart) -> dict:
    hint = cart_coin_hint(cart.total)
    payload = cart_coin_hint_payload(hint)
    return {
        "cart": cart,
        "cart_coin_hint": hint,
        "cart_coin_hint_message": payload["message"] if payload else None,
        "cart_coin_hint_parts": cart_coin_hint_parts(hint),
        "cart_coin_hint_coins": payload.get("coins") if payload else None,
    }


def cart_detail_view(request: HttpRequest) -> HttpResponse:
    cart = Cart(request)
    return render(request, "cart/cart.html", _cart_context(cart))


from apps.core.htmx import hx_trigger as _hx_trigger  # спільний ASCII-safe helper


def _cart_added_message(qty: int) -> str:
    if qty == 1:
        return _("Товар додано до кошика")
    return _("%(n)d товар(ів) додано до кошика.") % {"n": qty}


@require_POST
def cart_add_view(request: HttpRequest, product_id: int) -> HttpResponse:
    cart = Cart(request)
    qty = max(1, int(request.POST.get("qty", 1)))
    cart.add(product_id, qty)
    item = cart.peek(product_id)
    trigger: dict = {
        "cartUpdated": len(cart),
        "toast": {"message": _cart_added_message(qty), "type": "success"},
    }
    coin_payload = cart_coin_hint_payload(cart_coin_hint(cart.total))
    if coin_payload:
        trigger["svitik"] = svitik_event(
            coin_payload["message"],
            variant="choice",
            title=str(_("Класний вибір!")),
            coins=coin_payload.get("coins"),
        )
    if item:
        trigger["cart:add"] = cart_action_payload(
            product_id=item["product_id"],
            name=item["name"],
            price=item["price"],
            qty=qty,
        )
    return _hx_trigger(HttpResponse(status=204), trigger)


@require_POST
def cart_remove_view(request: HttpRequest, product_id: int) -> HttpResponse:
    cart = Cart(request)
    item = cart.peek(product_id)
    cart.remove(product_id)
    response = render(request, "cart/cart_body.html", _cart_context(cart))
    trigger: dict = {"cartUpdated": len(cart)}
    if item:
        trigger["cart:remove"] = cart_action_payload(
            product_id=item["product_id"],
            name=item["name"],
            price=item["price"],
            qty=item["qty"],
        )
    return _hx_trigger(response, trigger)


@require_POST
def cart_update_view(request: HttpRequest, product_id: int) -> HttpResponse:
    cart = Cart(request)
    qty = int(request.POST.get("qty", 1))
    cart.update_qty(product_id, qty)
    response = render(request, "cart/cart_body.html", _cart_context(cart))
    return _hx_trigger(response, {"cartUpdated": len(cart)})
