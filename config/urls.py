from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path, register_converter
from django.views.i18n import set_language

from apps.core.converters import UnicodeSlugConverter
from apps.core.views import service_worker
from apps.catalog.views import product_listing_image_view
from apps.seo.sitemaps import (
    BrandSitemap,
    CategorySitemap,
    PageSitemap,
    ProductSitemap,
    ServiceSitemap,
)

register_converter(UnicodeSlugConverter, "uslug")

sitemaps = {
    "products": ProductSitemap,
    "categories": CategorySitemap,
    "brands": BrandSitemap,
    "services": ServiceSitemap,
    "pages": PageSitemap,
}

urlpatterns = [
    path("healthz/", lambda request: HttpResponse("ok", content_type="text/plain")),
    path("i/<int:pk>.webp", product_listing_image_view, name="product_listing_image"),
    path("sw.js", service_worker, name="service_worker"),
    path("i18n/set-language/", set_language, name="set_language"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("robots.txt", include("apps.seo.urls_robots")),
    # Feeds
    path("feeds/", include("apps.analytics.feed_urls")),
    # API v1 (language-independent)
    path("api/v1/", include("apps.api.urls")),
    # Webhooks (language-independent)
    path("webhooks/", include("apps.integrations.webhook_urls")),
    # Push notifications
    path("notifications/", include("apps.notifications.urls")),
    # Bot webhook
    path("bot/", include("apps.bots.urls")),
    # Chat (WebSocket served via ASGI/Channels)
    path("chat/", include("apps.chat.urls")),
    # CKEditor 5 file uploads (admin rich text)
    path("ckeditor5/", include("django_ckeditor_5.urls")),
]

urlpatterns += i18n_patterns(
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("apps.catalog.urls")),
    path("search/", include("apps.search.urls")),
    path("cart/", include("apps.cart.urls")),
    path("checkout/", include("apps.checkout.urls")),
    path("pay/", include("apps.payments.urls")),
    path("account/", include("apps.customers.urls")),
    path("orders/", include("apps.orders.urls")),
    path("wishlist/", include("apps.wishlist.urls")),
    path("compare/", include("apps.compare.urls")),
    path("reviews/", include("apps.reviews.urls")),
    path("services/", include("apps.services.urls")),
    path("loyalty/", include("apps.loyalty.urls")),
    path("promotions/", include("apps.promotions.urls")),
    path("ai/", include("apps.ai.urls")),
    path("shipping/", include("apps.shipping.urls")),
    path("", include("apps.pages.urls")),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
