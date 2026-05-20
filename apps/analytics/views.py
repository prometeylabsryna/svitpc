"""Google Merchant Center XML feed."""

from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string

from apps.catalog.models import Product


def google_merchant_feed_view(request: HttpRequest) -> HttpResponse:
    products = Product.objects.filter(is_visible=True, stock__gt=0).select_related("brand").prefetch_related("categories")[:5000]
    content = render_to_string("analytics/merchant_feed.xml", {"products": products, "request": request})
    return HttpResponse(content, content_type="application/xml; charset=utf-8")


def google_ads_remarketing_feed_view(request: HttpRequest) -> HttpResponse:
    products = Product.objects.filter(is_visible=True).select_related("brand")[:5000]
    content = render_to_string("analytics/remarketing_feed.xml", {"products": products, "request": request})
    return HttpResponse(content, content_type="application/xml; charset=utf-8")
