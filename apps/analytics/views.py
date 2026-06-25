"""Google Merchant Center and Ads feed views."""

from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string

from .feeds import merchant_feed_queryset, remarketing_feed_queryset


def google_merchant_feed_view(request: HttpRequest) -> HttpResponse:
    products = merchant_feed_queryset()
    content = render_to_string(
        "analytics/merchant_feed.xml",
        {"products": products, "request": request},
    )
    return HttpResponse(content, content_type="application/xml; charset=utf-8")


def google_ads_remarketing_feed_view(request: HttpRequest) -> HttpResponse:
    products = remarketing_feed_queryset()
    content = render_to_string(
        "analytics/remarketing_feed.xml",
        {"products": products, "request": request},
    )
    return HttpResponse(content, content_type="application/xml; charset=utf-8")
