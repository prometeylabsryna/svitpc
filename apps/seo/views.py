from django.http import HttpRequest, HttpResponse

_PRIVATE_PATHS = [
    "/admin/",
    "/api/",
    "/cart/",
    "/checkout/",
    "/account/",
    "/orders/",
    "/pay/",
    "/bot/",
    "/feeds/",
    "/webhooks/",
    "/chat/",
    # English locale equivalents
    "/en/cart/",
    "/en/checkout/",
    "/en/account/",
    "/en/orders/",
    "/en/pay/",
]


def robots_txt_view(request: HttpRequest) -> HttpResponse:
    disallow_lines = "\n".join(f"Disallow: {p}" for p in _PRIVATE_PATHS)
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        f"{disallow_lines}\n"
        "Crawl-delay: 1\n"
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}\n"
    )
    return HttpResponse(content, content_type="text/plain")
