"""Query helpers for service catalog pages."""

from __future__ import annotations

from django.db.models import Prefetch, QuerySet

from .models import PriceItem, Service, ServiceCategory


def active_services_prefetch() -> Prefetch:
    return Prefetch(
        "services",
        queryset=(
            Service.objects.filter(is_active=True)
            .prefetch_related(
                Prefetch("prices", queryset=PriceItem.objects.order_by("sort_order"))
            )
            .order_by("sort_order")
        ),
    )


def active_service_categories() -> QuerySet[ServiceCategory]:
    return (
        ServiceCategory.objects.prefetch_related(active_services_prefetch())
        .filter(services__is_active=True)
        .distinct()
        .order_by("sort_order")
    )


def home_featured_services(limit: int = 3) -> QuerySet[Service]:
    return (
        Service.objects.filter(is_active=True, show_on_home=True)
        .select_related("category")
        .order_by("sort_order")[:limit]
    )
