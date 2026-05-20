"""Admin for services app."""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from .models import PriceItem, Service, ServiceCategory, ServiceRequest


class PriceInline(TabularInline):
    model = PriceItem
    extra = 0
    fields = ("name", "price_from", "price_to", "price_text", "sort_order")


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(ModelAdmin):
    list_display = ("name", "slug", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("sort_order",)
    fieldsets = (
        (None, {"fields": ("name", "name_en", "slug", "sort_order")}),
    )


@admin.register(Service)
class ServiceAdmin(ModelAdmin):
    list_display = ("name", "category", "is_active", "sort_order", "thumb_preview")
    list_filter = ("is_active", "category")
    search_fields = ("name", "name_en", "slug")
    list_editable = ("is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("thumb_preview",)
    inlines = [PriceInline]
    fieldsets = (
        (None, {
            "fields": ("category", "name", "name_en", "slug", "is_active", "sort_order"),
        }),
        (_("Опис"), {
            "fields": ("description", "description_en"),
        }),
        (_("Фото"), {
            "fields": ("image", "thumb_preview"),
        }),
        (_("SEO"), {
            "fields": ("seo_title", "seo_description"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description=_("Фото"))
    def thumb_preview(self, obj: Service) -> str:
        if obj.image:
            return format_html('<img src="{}" width="80" height="60" style="object-fit:contain">', obj.image.url)
        return "—"


@admin.register(ServiceRequest)
class ServiceRequestAdmin(ModelAdmin):
    list_display = ("id", "customer_name", "customer_phone", "device", "service", "status", "created_at")
    list_filter = ("status", "service")
    search_fields = ("customer_name", "customer_phone", "device")
    list_editable = ("status",)
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    actions = ["mark_in_progress", "mark_ready", "mark_done"]
    fieldsets = (
        (_("Клієнт"), {
            "fields": ("customer", "customer_name", "customer_phone"),
        }),
        (_("Заявка"), {
            "fields": ("service", "device", "description", "status"),
        }),
        (_("Внутрішнє"), {
            "fields": ("technician_notes", "estimated_cost", "final_cost", "telegram_chat_id"),
        }),
        (_("Дати"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.action(description=_("Позначити «В роботі»"))
    def mark_in_progress(self, request, queryset):
        queryset.update(status=ServiceRequest.STATUS_IN_PROGRESS)

    @admin.action(description=_("Позначити «Готова до видачі»"))
    def mark_ready(self, request, queryset):
        queryset.update(status=ServiceRequest.STATUS_READY)

    @admin.action(description=_("Позначити «Видана»"))
    def mark_done(self, request, queryset):
        queryset.update(status=ServiceRequest.STATUS_DONE)
