from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import Promotion
from .services import running_promotions_qs


def promotions_list_view(request: HttpRequest) -> HttpResponse:
    promotions = (
        running_promotions_qs()
        .select_related("product", "product__brand")
        .prefetch_related("product__images")
        .order_by("end_date")
    )
    return render(request, "promotions/promotion_list.html", {"promotions": promotions})
