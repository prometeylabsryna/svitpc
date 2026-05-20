from django.apps import AppConfig


class OrdersConfig(AppConfig):
    name = "apps.orders"
    verbose_name = "Orders"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        import apps.orders.signals  # noqa: F401
