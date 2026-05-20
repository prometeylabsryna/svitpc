from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .cart import Cart


def cart_detail_view(request: HttpRequest) -> HttpResponse:
    cart = Cart(request)
    return render(request, "cart/cart.html", {"cart": cart})


@require_POST
def cart_add_view(request: HttpRequest, product_id: int) -> HttpResponse:
    cart = Cart(request)
    qty = int(request.POST.get("qty", 1))
    cart.add(product_id, qty)
    response = HttpResponse(status=204)
    response["HX-Trigger"] = f'{{"cartUpdated": {len(cart)}}}'
    return response


@require_POST
def cart_remove_view(request: HttpRequest, product_id: int) -> HttpResponse:
    cart = Cart(request)
    cart.remove(product_id)
    return render(request, "cart/cart_items.html", {"cart": cart})


@require_POST
def cart_update_view(request: HttpRequest, product_id: int) -> HttpResponse:
    cart = Cart(request)
    qty = int(request.POST.get("qty", 1))
    cart.update_qty(product_id, qty)
    return render(request, "cart/cart_items.html", {"cart": cart})
