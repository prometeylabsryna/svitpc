from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from apps.loyalty.coins import coins_for_order

from .models import Order


@login_required
def order_list_view(request: HttpRequest) -> HttpResponse:
    orders = request.user.orders.select_related("status").prefetch_related("items").order_by("-created_at")
    return render(request, "orders/order_list.html", {"orders": orders})


@login_required
def order_detail_view(request: HttpRequest, pk: int) -> HttpResponse:
    from apps.loyalty.models import BonusTransaction

    order = get_object_or_404(
        Order.objects.select_related("status"),
        pk=pk,
        customer=request.user,
    )
    pending_coins = 0
    if not order.status.is_completed and not BonusTransaction.objects.filter(
        order=order,
        transaction_type=BonusTransaction.TYPE_EARN,
    ).exists():
        pending_coins = coins_for_order(order)
    return render(
        request,
        "orders/order_detail.html",
        {"order": order, "pending_coins": pending_coins},
    )


@login_required
def reorder_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Add all items from a past order back into the cart, then redirect to cart."""
    from apps.cart.cart import Cart
    from apps.catalog.models import Product

    order = get_object_or_404(Order, pk=pk, customer=request.user)
    cart = Cart(request)
    added = 0

    for item in order.items.select_related("product").all():
        product = getattr(item, "product", None)
        if not product:
            try:
                product = Product.objects.get(pk=item.product_id)
            except Product.DoesNotExist:
                continue
        if product.is_available:
            cart.add(product.pk, qty=item.qty, override=False)
            added += 1

    if added:
        messages.success(request, _("%(n)d товар(ів) додано до кошика.") % {"n": added})
    else:
        messages.warning(request, _("Товари зі старого замовлення недоступні."))

    return redirect("cart:detail")
