from __future__ import annotations

from django.db.models import Prefetch, QuerySet
from django.utils import timezone

from apps.catalog.models import Product

from .models import Promotion


def running_promotions_qs() -> QuerySet[Promotion]:
    now = timezone.now()
    return Promotion.objects.filter(
        is_active=True,
        start_date__lte=now,
        end_date__gte=now,
    )


def with_active_promotions(qs: QuerySet[Product]) -> QuerySet[Product]:
    """Prefetch running promotions as ``product.active_promotions``."""
    return qs.prefetch_related(
        Prefetch("promotions", queryset=running_promotions_qs(), to_attr="active_promotions")
    )
