from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import Promotion


def promotions_list_view(request: HttpRequest) -> HttpResponse:
    promotions = (
        Promotion.objects.filter(is_active=True)
        .order_by("sort_order")
        .prefetch_related("products__brand", "products__images")
    )
    return render(request, "promotions/list.html", {"promotions": promotions})
