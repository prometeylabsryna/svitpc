from decimal import Decimal

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import NovaPoshtaCity, NovaPoshtaWarehouse
from .services import calc_delivery_cost


def np_cities_view(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("city", "").strip()
    cities = NovaPoshtaCity.objects.filter(name__icontains=q)[:10] if len(q) >= 2 else []
    return render(request, "shipping/partials/city_results.html", {"cities": cities})


def np_warehouses_view(request: HttpRequest) -> HttpResponse:
    city_ref = request.GET.get("city_ref", "").strip()
    q = request.GET.get("warehouse", "").strip()
    warehouses = []
    if city_ref:
        qs = NovaPoshtaWarehouse.objects.filter(city__ref=city_ref)
        if q:
            qs = qs.filter(name__icontains=q)
        warehouses = qs[:20]
    return render(request, "shipping/partials/warehouse_results.html", {"warehouses": warehouses})


def delivery_cost_view(request: HttpRequest) -> HttpResponse:
    """HTMX partial — calculate and return delivery cost."""
    delivery_type = request.GET.get("delivery_type", "nova_poshta")
    city_ref = request.GET.get("city_ref", "")
    warehouse_ref = request.GET.get("warehouse_ref", "")
    try:
        cart_total = Decimal(request.GET.get("total", "500"))
    except Exception:
        cart_total = Decimal("500")

    cost = calc_delivery_cost(
        delivery_type=delivery_type,
        city_ref=city_ref,
        warehouse_ref=warehouse_ref,
        declared_value=cart_total,
    )
    return render(request, "shipping/partials/delivery_cost.html", {"cost": cost})
