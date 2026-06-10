"""Fixed order statuses shown in admin."""

from __future__ import annotations

ORDER_STATUS_NAMES: tuple[str, ...] = ("Нове", "В процесі", "Виконано")

ORDER_STATUSES: tuple[tuple[str, str, int, bool, str], ...] = (
    ("Нове", "New", 1, False, "#6b7280"),
    ("В процесі", "In progress", 2, False, "#f59e0b"),
    ("Виконано", "Completed", 3, True, "#22c55e"),
)


def admin_status_queryset():
    from apps.orders.models import OrderStatus

    return OrderStatus.objects.filter(name__in=ORDER_STATUS_NAMES).order_by("sort_order")
