"""Admin registration for promotions app: Promotion, Banner, HomeAdSettings."""

import json

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .home_ads import (
    all_aspect_labels,
    all_recommended_sizes,
    aspect_ratio_label,
    recommended_banner_size,
)
from .models import Banner, HomeAdSettings, Promotion


@admin.register(Promotion)
class PromotionAdmin(ModelAdmin):
    list_display = (
        "title_uk",
        "product",
        "start_date",
        "end_date",
        "is_active",
        "is_running_display",
        "auto_synced_display",
    )
    list_filter = ("is_active", "auto_synced")
    list_editable = ("is_active",)
    date_hierarchy = "end_date"
    search_fields = ("title_uk", "title_en", "product__name_uk", "product__name_en")
    readonly_fields = ("auto_synced",)
    autocomplete_fields = ("product",)
    actions = ["send_push_notification"]
    fieldsets = (
        (
            _("Загальне"),
            {"fields": ("product", "start_date", "end_date", "is_active", "auto_synced")},
        ),
        (
            _("🇺🇦 Українська"),
            {"fields": ("title_uk", "description_uk")},
        ),
        (
            _("🇬🇧 English"),
            {"fields": ("title_en", "description_en")},
        ),
    )

    @admin.display(description=_("Статус"))
    def is_running_display(self, obj: Promotion) -> str:
        if obj.is_running:
            return format_html('<span class="admin-status admin-status--ok">✓ {}</span>', _("Діє"))
        return format_html('<span class="admin-status admin-status--bad">✕ {}</span>', _("Не діє"))

    @admin.display(description=_("Джерело"))
    def auto_synced_display(self, obj: Promotion) -> str:
        if obj.auto_synced:
            return format_html('<span class="admin-status admin-status--info">⚙ {}</span>', _("Авто"))
        return "—"

    @admin.action(description=_("Надіслати push-повідомлення про акцію"))
    def send_push_notification(self, request, queryset):
        from apps.notifications.tasks import notify_promotion_push

        n = 0
        for promo in queryset:
            notify_promotion_push.delay(promo.pk)
            n += 1
        self.message_user(request, _("Push-розсилку поставлено в чергу: %(n)d акцій") % {"n": n})


@admin.register(HomeAdSettings)
class HomeAdSettingsAdmin(ModelAdmin):
    readonly_fields = ("image_size_hint", "banners_link")
    fields = ("visible_columns", "image_size_hint", "banners_link")

    class Media:
        js = ("admin/js/home_ad_settings.js",)

    def has_add_permission(self, request) -> bool:
        return not HomeAdSettings.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def changelist_view(self, request, extra_context=None):
        settings = HomeAdSettings.load()
        return self.change_view(request, str(settings.pk), extra_context=extra_context)

    @admin.display(description=_("Рекомендований розмір зображення"))
    def image_size_hint(self, obj: HomeAdSettings) -> str:
        cols = obj.visible_columns
        w, h = recommended_banner_size(cols)
        ratio = aspect_ratio_label(cols)
        sizes_json = json.dumps(
            {str(k): [v[0], v[1]] for k, v in all_recommended_sizes().items()}
        )
        ratios_json = json.dumps(all_aspect_labels())
        return format_html(
            '<p id="home-ad-size-hint" class="help" data-sizes="{}" data-ratios="{}">'
            "{}: <strong data-size-dims>{} × {} px</strong> "
            '(<span data-size-ratio>{}</span>). '
            "{}"
            "</p>",
            sizes_json,
            ratios_json,
            _("Для обраної кількості колонок"),
            w,
            h,
            ratio,
            _(
                "Завантажуйте банери з позицією «Головна» у розділі «Банери». "
                "Один банер — широка смуга (20:7), трохи вища за ряд із 4 плиток. "
                "На мобільному при 2–4 колонках — 3:4."
            ),
        )

    @admin.display(description=_("Банери"))
    def banners_link(self, obj: HomeAdSettings) -> str:
        url = reverse("admin:promotions_banner_changelist") + "?position__exact=home"
        add_url = reverse("admin:promotions_banner_add") + "?position=home"
        return format_html(
            '<p><a href="{}">{}</a> · <a href="{}">{}</a></p>',
            url,
            _("Переглянути банери для головної"),
            add_url,
            _("Додати банер"),
        )


@admin.register(Banner)
class BannerAdmin(ModelAdmin):
    list_display = ("title", "position", "is_active", "sort_order", "date_start", "date_end")
    list_filter = ("is_active", "position")
    search_fields = ("title",)
    list_editable = ("is_active", "sort_order", "position")
    date_hierarchy = "date_start"
    actions = ["activate", "deactivate"]
    readonly_fields = ("home_size_hint",)

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "position",
                    "image",
                    "image_mobile",
                    "link",
                    "is_active",
                    "sort_order",
                    "date_start",
                    "date_end",
                ),
            },
        ),
        (
            _("Підказка для головної"),
            {
                "fields": ("home_size_hint",),
                "classes": ("collapse",),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if "home_size_hint" not in fields:
            fields.append("home_size_hint")
        return fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        position = None
        if request.method == "POST":
            position = request.POST.get("position")
        elif obj:
            position = obj.position
        if position != Banner.POSITION_HOME:
            return fieldsets[:1]
        return fieldsets

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if request.GET.get("position") == Banner.POSITION_HOME:
            initial["position"] = Banner.POSITION_HOME
        return initial

    @admin.display(description=_("Розмір для головної"))
    def home_size_hint(self, obj: Banner | None) -> str:
        settings = HomeAdSettings.load()
        cols = settings.visible_columns
        w, h = recommended_banner_size(cols)
        ratio = aspect_ratio_label(cols)
        return format_html(
            '<p class="help">{}: <strong>{} × {} px</strong> ({}) — {} {}.</p>',
            _("Рекомендований розмір"),
            w,
            h,
            ratio,
            _("зараз на головній"),
            cols,
            _("колонки"),
        )

    @admin.action(description=_("Активувати обрані банери"))
    def activate(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, _("Активовано: %(n)d") % {"n": updated})

    @admin.action(description=_("Деактивувати обрані банери"))
    def deactivate(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _("Деактивовано: %(n)d") % {"n": updated})
