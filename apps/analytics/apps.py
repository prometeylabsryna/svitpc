from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    name = "apps.analytics"
    verbose_name = "Analytics"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from . import admin as analytics_admin  # noqa: F401
