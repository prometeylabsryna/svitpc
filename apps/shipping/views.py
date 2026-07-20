from decimal import Decimal

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .services import calc_delivery_cost, search_np_cities, search_np_warehouses


def np_cities_view(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("city", "").strip()
    cities = search_np_cities(q)
    return render(request, "shipping/partials/city_results.html", {"cities": cities})


def np_warehouses_view(request: HttpRequest) -> HttpResponse:
    city_ref = request.GET.get("city_ref", "").strip()
    q = request.GET.get("warehouse", "").strip()
    warehouses = search_np_warehouses(city_ref, q) if city_ref else []
    return render(request, "shipping/partials/warehouse_results.html", {"warehouses": warehouses})


def delivery_cost_view(request: HttpRequest) -> HttpResponse:
    """HTMX partial — calculate and return delivery cost."""
    delivery_type = request.GET.get("delivery_type", "nova_poshta")
    city_ref = request.GET.get("city_ref", "")
    warehouse_ref = request.GET.get("warehouse_ref", "")
    try:
        weight_kg = float(request.GET.get("weight", "1") or 1)
    except (TypeError, ValueError):
        weight_kg = 1.0
    try:
        cart_total = Decimal(request.GET.get("total", "500"))
    except Exception:
        cart_total = Decimal("500")

    cost = calc_delivery_cost(
        delivery_type=delivery_type,
        city_ref=city_ref,
        warehouse_ref=warehouse_ref,
        weight_kg=weight_kg,
        declared_value=cart_total,
    )
    return render(
        request,
        "shipping/partials/delivery_cost.html",
        {"cost": cost, "delivery_type": delivery_type},
    )
