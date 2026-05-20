"""Checkout wizard: step1 (delivery) → step2 (payment) → confirm + 1-Click."""

from __future__ import annotations

import logging

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

from apps.cart.cart import Cart
from apps.catalog.models import Product
from apps.orders.models import Order, OrderItem, OrderStatus


def _default_status() -> OrderStatus:
    return OrderStatus.objects.order_by("sort_order").first() or OrderStatus.objects.create(name="Нове", sort_order=0)


def checkout_step1_view(request: HttpRequest) -> HttpResponse:
    """Step 1: contact + delivery info."""
    cart = Cart(request)
    if not len(cart):
        return redirect("cart:detail")

    prefill = {}
    if request.user.is_authenticated:
        u = request.user
        prefill = {"first_name": u.first_name, "last_name": u.last_name, "email": u.email, "phone": u.phone}

    if request.method == "POST":
        request.session["checkout_step1"] = request.POST.dict()
        return redirect("checkout:step2")

    return render(request, "checkout/step1.html", {"cart": cart, "prefill": prefill})


def checkout_step2_view(request: HttpRequest) -> HttpResponse:
    """Step 2: payment selection."""
    cart = Cart(request)
    if not len(cart):
        return redirect("cart:detail")
    step1 = request.session.get("checkout_step1", {})
    if not step1:
        return redirect("checkout:step1")

    if request.method == "POST":
        request.session["checkout_step2"] = request.POST.dict()
        return redirect("checkout:confirm")

    return render(request, "checkout/step2.html", {
        "cart": cart,
        "step1": step1,
        "payment_choices": Order.PAYMENT_CHOICES,
    })


def checkout_confirm_view(request: HttpRequest) -> HttpResponse:
    cart = Cart(request)
    step1 = request.session.get("checkout_step1", {})
    step2 = request.session.get("checkout_step2", {})
    if not step1 or not step2 or not len(cart):
        return redirect("checkout:step1")

    if request.method == "POST":
        from decimal import Decimal
        from apps.shipping.services import calc_delivery_cost

        delivery_type = step1.get("delivery_type", "nova_poshta")
        delivery_cost = calc_delivery_cost(
            delivery_type=delivery_type,
            city_ref=step1.get("city_ref", ""),
            warehouse_ref=step1.get("warehouse_ref", ""),
            declared_value=Decimal(str(cart.total)),
        )

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
            total=cart.total,
            delivery_cost=delivery_cost,
        )
        for item in cart:
            OrderItem.objects.create(
                order=order,
                product_id=item["product_id"],
                name=item["name"],
                price=item["price"],
                qty=item["qty"],
            )
        cart.clear()
        del request.session["checkout_step1"]
        del request.session["checkout_step2"]

        try:
            from apps.notifications.tasks import notify_new_order
            notify_new_order.delay(order.pk)
        except Exception:
            logger.exception("Failed to dispatch notify_new_order for order %s", order.pk)

        try:
            if delivery_type == Order.DELIVERY_NP:
                from apps.shipping.tasks import create_ttn_for_order
                create_ttn_for_order.delay(order.pk)
            elif delivery_type == Order.DELIVERY_UP:
                from apps.integrations.ukrposhta.tasks import create_up_shipment_for_order
                create_up_shipment_for_order.delay(order.pk)
        except Exception:
            logger.exception("Failed to dispatch shipment task for order %s", order.pk)

        if order.payment_method == Order.PAYMENT_CASH_ON_DELIVERY:
            return redirect("checkout:success", pk=order.pk)

        from django.urls import reverse
        return redirect(
            reverse("payments:initiate", kwargs={"order_id": order.pk}) + "?provider=liqpay"
        )

    return render(request, "checkout/confirm.html", {"cart": cart, "step1": step1, "step2": step2})


def checkout_success_view(request: HttpRequest, pk: int) -> HttpResponse:
    order = get_object_or_404(Order, pk=pk)
    return render(request, "checkout/success.html", {"order": order})


def one_click_view(request: HttpRequest, product_id: int) -> HttpResponse:
    """HTMX partial — 1-Click buy form."""
    product = get_object_or_404(Product, pk=product_id, is_visible=True)
    if request.method == "POST":
        phone = request.POST.get("phone", "").strip()
        name = request.POST.get("name", "").strip()
        if phone and name:
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
            try:
                from apps.notifications.tasks import notify_new_order
                notify_new_order.delay(order.pk)
            except Exception:
                logger.exception("Failed to dispatch notify_new_order for order %s", order.pk)
            return render(request, "checkout/one_click_success.html", {"order": order, "product": product})
    return render(request, "checkout/one_click_form.html", {"product": product})
