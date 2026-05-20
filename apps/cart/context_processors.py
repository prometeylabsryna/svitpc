from django.http import HttpRequest

from .cart import Cart


def cart_context(request: HttpRequest) -> dict:
    cart = Cart(request)
    return {"cart": cart, "cart_count": len(cart)}
