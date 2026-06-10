from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import Service
from .querysets import active_service_categories, home_featured_services


def service_list_view(request: HttpRequest) -> HttpResponse:
    categories = active_service_categories()
    return render(request, "services/list.html", {"categories": categories})


def service_prices_view(request: HttpRequest) -> HttpResponse:
    categories = active_service_categories()
    return render(request, "services/prices.html", {"categories": categories})


def service_detail_view(request: HttpRequest, slug: str) -> HttpResponse:
    service = get_object_or_404(
        Service.objects.prefetch_related("prices"),
        slug=slug,
        is_active=True,
    )
    return render(request, "services/detail.html", {"service": service})
