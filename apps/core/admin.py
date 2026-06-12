"""Admin for core app."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(ModelAdmin):
    autocomplete_fields = ("used_category",)
    fieldsets = (
        (
            _("Контакти"),
            {
                "fields": ("name", "name_en", "phone", "viber_phone", "email", "address"),
            },
        ),
        (
            _("Юридична інформація"),
            {
                "fields": ("legal_entity", "legal_name", "tax_id", "legal_address"),
                "description": _(
                    "Відображається у футері та на сторінках контактів/оплати. "
                    "Дані мають збігатися з документами в кабінеті LiqPay."
                ),
            },
        ),
        (
            _("Тексти"),
            {
                "fields": ("tagline", "tagline_en"),
            },
        ),
        (
            _("Соцмережі"),
            {
                "fields": ("facebook_url", "instagram_url", "telegram_url"),
                "description": _(
                    "Посилання з’являться у футері лише якщо поле заповнене. "
                    "Бот для чату на сайті налаштовується окремо (TELEGRAM_BOT_LINK у .env)."
                ),
            },
        ),
        (
            _("Каталог"),
            {
                "fields": ("used_category", "show_used_category"),
                "description": _(
                    "Керує видимістю розділу вживаної техніки (Б/У) у меню та на сторінках каталогу. "
                    "Товари в категорії залишаються в базі — змінюється лише показ на сайті."
                ),
            },
        ),
    )

    def has_add_permission(self, request) -> bool:
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def changelist_view(self, request, extra_context=None):
        settings_obj = SiteSettings.load()
        return self.change_view(request, str(settings_obj.pk), extra_context=extra_context)
