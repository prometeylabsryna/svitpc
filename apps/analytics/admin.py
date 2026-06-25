"""Register custom admin URLs for analytics (no DB models)."""

from __future__ import annotations

from django.contrib import admin
from django.urls import path

from .admin_views import FeedsDashboardView

_ANALYTICS_ADMIN_URLS_PATCHED = False


def _patch_admin_urls() -> None:
    global _ANALYTICS_ADMIN_URLS_PATCHED
    if _ANALYTICS_ADMIN_URLS_PATCHED:
        return

    original_get_urls = admin.site.get_urls

    def get_urls():
        custom = [
            path(
                "marketing/feeds/",
                admin.site.admin_view(FeedsDashboardView.as_view()),
                name="analytics_feeds_dashboard",
            ),
        ]
        return custom + original_get_urls()

    admin.site.get_urls = get_urls
    _ANALYTICS_ADMIN_URLS_PATCHED = True


_patch_admin_urls()
