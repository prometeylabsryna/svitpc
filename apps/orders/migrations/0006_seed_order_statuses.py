"""Seed default order statuses: Нове, В процесі, Виконано."""

from django.db import migrations

STATUSES = (
    ("Нове", "New", 1, False, "#6b7280"),
    ("В процесі", "In progress", 2, False, "#f59e0b"),
    ("Виконано", "Completed", 3, True, "#22c55e"),
)


def seed_statuses(apps, schema_editor):
    OrderStatus = apps.get_model("orders", "OrderStatus")
    Order = apps.get_model("orders", "Order")

    by_name: dict[str, object] = {}
    for name, name_en, sort_order, is_completed, color in STATUSES:
        status, _ = OrderStatus.objects.update_or_create(
            name=name,
            defaults={
                "name_en": name_en,
                "sort_order": sort_order,
                "is_completed": is_completed,
                "color": color,
            },
        )
        by_name[name] = status

    for order in Order.objects.select_related("status").iterator():
        if order.status.name in by_name:
            continue
        if order.status.is_completed:
            order.status = by_name["Виконано"]
        elif any(word in order.status.name.lower() for word in ("процес", "відправ", "оброб")):
            order.status = by_name["В процесі"]
        else:
            order.status = by_name["Нове"]
        order.save(update_fields=["status"])


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0005_order_email_optional"),
    ]

    operations = [
        migrations.RunPython(seed_statuses, migrations.RunPython.noop),
    ]
