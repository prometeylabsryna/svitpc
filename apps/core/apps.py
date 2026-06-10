from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    verbose_name = "Ядро"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from django.utils.translation import gettext_lazy as _
        from unfold.admin import ModelAdmin

        _original_get_action_choices = ModelAdmin.get_action_choices

        def get_action_choices(self, request, default_choices=None):
            return _original_get_action_choices(
                self,
                request,
                [("", _("Виберіть дію"))],
            )

        ModelAdmin.get_action_choices = get_action_choices
