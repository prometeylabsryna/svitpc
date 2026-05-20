"""Admin registration for promotions app: Promotion, Banner."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import Banner, Promotion


@admin.register(Promotion)
class PromotionAdmin(ModelAdmin):
    list_display = ("name", "is_active", "date_start", "date_end", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "name_en", "slug")
    list_editable = ("is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("products",)
    date_hierarchy = "date_start"
    actions = ["activate", "deactivate", "send_push_notification"]

    @admin.action(description=_("Активувати обрані акції"))
    def activate(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, _("Активовано: %(n)d") % {"n": updated})

    @admin.action(description=_("Деактивувати обрані акції"))
    def deactivate(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _("Деактивовано: %(n)d") % {"n": updated})

    @admin.action(description=_("Надіслати push-повідомлення про акцію"))
    def send_push_notification(self, request, queryset):
        from apps.notifications.tasks import notify_promotion_push

        n = 0
        for promo in queryset:
            notify_promotion_push.delay(promo.pk)
            n += 1
        self.message_user(request, _("Push-розсилку поставлено в чергу: %(n)d акцій") % {"n": n})


@admin.register(Banner)
class BannerAdmin(ModelAdmin):
    list_display = ("title", "position", "is_active", "sort_order", "date_start", "date_end")
    list_filter = ("is_active", "position")
    search_fields = ("title",)
    list_editable = ("is_active", "sort_order", "position")
    date_hierarchy = "date_start"
    actions = ["activate", "deactivate"]

    @admin.action(description=_("Активувати обрані банери"))
    def activate(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, _("Активовано: %(n)d") % {"n": updated})

    @admin.action(description=_("Деактивувати обрані банери"))
    def deactivate(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _("Деактивовано: %(n)d") % {"n": updated})
