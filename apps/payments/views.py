"""Payment views — stubs for LiqPay/WayForPay/Monobank."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.orders.models import Order

from .models import Payment


def initiate_payment_view(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(Order, pk=order_id)
    provider = request.GET.get("provider", "liqpay")
    # Build payment form data per provider
    from apps.integrations.payments import get_payment_provider
    prov = get_payment_provider(provider)
    form_data = prov.create_payment(order)
    return render(request, "payments/redirect.html", {"form_data": form_data, "provider": provider, "order": order})


@csrf_exempt
@require_POST
def liqpay_webhook_view(request: HttpRequest) -> HttpResponse:
    from apps.integrations.payments.liqpay import LiqPayProvider
    LiqPayProvider().handle_webhook(request.POST)
    return HttpResponse("OK")


@csrf_exempt
@require_POST
def wayforpay_webhook_view(request: HttpRequest) -> HttpResponse:
    from apps.integrations.payments.wayforpay import WayForPayProvider
    WayForPayProvider().handle_webhook(request.body)
    return HttpResponse("OK")


@csrf_exempt
@require_POST
def monobank_webhook_view(request: HttpRequest) -> HttpResponse:
    from apps.integrations.payments.monobank import MonobankProvider
    MonobankProvider().handle_webhook(request.body)
    return HttpResponse("OK")
