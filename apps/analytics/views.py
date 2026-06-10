"""Google Merchant Center and Ads feed views."""

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string

from apps.catalog.models import Product


def _feed_products(*, in_stock_only: bool = False):
    qs = (
        Product.objects.filter(is_visible=True)
        .select_related("brand")
        .prefetch_related("categories")
    )
    if in_stock_only:
        qs = qs.filter(stock__gt=0)
    max_items = getattr(settings, "ANALYTICS_FEED_MAX_PRODUCTS", 10000)
    return qs.order_by("pk")[:max_items]


def google_merchant_feed_view(request: HttpRequest) -> HttpResponse:
    products = _feed_products(in_stock_only=True)
    content = render_to_string(
        "analytics/merchant_feed.xml",
        {"products": products, "request": request},
    )
    return HttpResponse(content, content_type="application/xml; charset=utf-8")


def google_ads_remarketing_feed_view(request: HttpRequest) -> HttpResponse:
    products = _feed_products(in_stock_only=False)
    content = render_to_string(
        "analytics/remarketing_feed.xml",
        {"products": products, "request": request},
    )
    return HttpResponse(content, content_type="application/xml; charset=utf-8")
