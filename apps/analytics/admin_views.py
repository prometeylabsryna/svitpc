"""Staff-only admin dashboard for the Google Merchant Center feed."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View

from .feeds import FEED_DEFINITIONS, absolute_feed_url, collect_feed_stats


@method_decorator(staff_member_required, name="dispatch")
class FeedsDashboardView(View):
    """Marketing feed overview — URL, stats, GMC setup hints."""

    def get(self, request):
        stats = collect_feed_stats(request)

        feeds = [
            {
                "definition": definition,
                "url": absolute_feed_url(request, definition.slug),
                "issues": stats.merchant_issues,
                "product_count": stats.merchant_in_feed,
            }
            for definition in FEED_DEFINITIONS
        ]

        return render(
            request,
            "admin/analytics/feeds_dashboard.html",
            {
                "title": _("Фід Google Merchant Center"),
                "stats": stats,
                "feeds": feeds,
                **admin.site.each_context(request),
            },
        )
