from django.http import HttpRequest

from apps.core.admin_mixins import is_admin_request

from .cart import Cart


def cart_context(request: HttpRequest) -> dict:
    if is_admin_request(request):
        return {}
    cart = Cart(request)
    return {"cart": cart, "cart_count": len(cart)}
