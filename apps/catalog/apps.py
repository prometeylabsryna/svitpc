from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = "apps.catalog"
    verbose_name = "Catalog"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        import apps.catalog.signals  # noqa: F401
        import apps.catalog.translation  # noqa: F401
