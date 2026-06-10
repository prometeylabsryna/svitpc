from django.apps import AppConfig


class PromotionsConfig(AppConfig):
    name = "apps.promotions"
    verbose_name = "Promotions"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        import apps.promotions.signals  # noqa: F401
