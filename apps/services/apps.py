from django.apps import AppConfig


class ServicesConfig(AppConfig):
    name = "apps.services"
    verbose_name = "Services"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        import apps.services.signals  # noqa: F401
