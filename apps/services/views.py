from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import Service, ServiceCategory


def service_list_view(request: HttpRequest) -> HttpResponse:
    categories = ServiceCategory.objects.prefetch_related("services").filter(services__is_active=True).distinct().order_by("sort_order")
    return render(request, "services/list.html", {"categories": categories})


def service_detail_view(request: HttpRequest, slug: str) -> HttpResponse:
    service = get_object_or_404(Service, slug=slug, is_active=True)
    return render(request, "services/detail.html", {"service": service})
