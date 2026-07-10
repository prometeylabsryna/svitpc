"""Google Merchant Center feed view."""

from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string

from .feeds import merchant_feed_queryset

_MERCHANT_TEMPLATE = "analytics/merchant_feed.xml"


def _xml_response(template: str, context: dict) -> HttpResponse:
    content = render_to_string(template, context)
    return HttpResponse(content, content_type="application/xml; charset=utf-8")


def google_merchant_feed_view(request: HttpRequest) -> HttpResponse:
    return _xml_response(_MERCHANT_TEMPLATE, {"products": merchant_feed_queryset(), "request": request})
