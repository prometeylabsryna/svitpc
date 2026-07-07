"""Google Merchant Center and Ads feed views."""

from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string

from .feeds import (
    merchant_feed_cheap_queryset,
    merchant_feed_expensive_queryset,
    merchant_feed_medium_queryset,
    merchant_feed_queryset,
    remarketing_feed_queryset,
)

_MERCHANT_TEMPLATE = "analytics/merchant_feed.xml"
_REMARKETING_TEMPLATE = "analytics/remarketing_feed.xml"


def _xml_response(template: str, context: dict) -> HttpResponse:
    content = render_to_string(template, context)
    return HttpResponse(content, content_type="application/xml; charset=utf-8")


def google_merchant_feed_view(request: HttpRequest) -> HttpResponse:
    return _xml_response(_MERCHANT_TEMPLATE, {"products": merchant_feed_queryset(), "request": request})


def google_ads_remarketing_feed_view(request: HttpRequest) -> HttpResponse:
    return _xml_response(_REMARKETING_TEMPLATE, {"products": remarketing_feed_queryset(), "request": request})


def google_merchant_cheap_feed_view(request: HttpRequest) -> HttpResponse:
    return _xml_response(_MERCHANT_TEMPLATE, {"products": merchant_feed_cheap_queryset(), "request": request})


def google_merchant_medium_feed_view(request: HttpRequest) -> HttpResponse:
    return _xml_response(_MERCHANT_TEMPLATE, {"products": merchant_feed_medium_queryset(), "request": request})


def google_merchant_expensive_feed_view(request: HttpRequest) -> HttpResponse:
    return _xml_response(_MERCHANT_TEMPLATE, {"products": merchant_feed_expensive_queryset(), "request": request})
