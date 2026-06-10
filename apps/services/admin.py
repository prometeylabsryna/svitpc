"""Admin for services app."""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from .models import PriceItem, ProductSerial, Service, ServiceCategory, ServiceRequest, WarrantyClaim


class PriceInline(TabularInline):
    model = PriceItem
    extra = 1
    fields = ("name", "name_en", "price_from", "price_to", "price_text", "unit", "excludes_materials", "sort_order")
    ordering = ("sort_order",)


@admin.register(PriceItem)
class PriceItemAdmin(ModelAdmin):
    list_display = ("name", "service", "price_from", "price_to", "unit", "excludes_materials", "price_text", "display_price_col", "sort_order")
    list_filter = ("service__category", "service")
    search_fields = ("name", "name_en", "service__name")
    autocomplete_fields = ("service",)
    ordering = ("service__category__sort_order", "service__sort_order", "sort_order")
    fieldsets = (
        (None, {
            "fields": ("service", "name", "name_en", "sort_order"),
        }),
        (_("Ціна"), {
            "fields": ("price_from", "price_to", "price_text", "unit", "excludes_materials"),
            "description": _("Заповніть діапазон «від/до» або вільний текст ціни (наприклад «за домовленістю»)."),
        }),
    )

    @admin.display(description=_("Відображення"))
    def display_price_col(self, obj: PriceItem) -> str:
        return obj.display_price or "—"


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
    class Media:
        css = {"all": ("css/admin_extra.css",)}

    list_display = ("name", "category", "is_active", "show_on_home", "sort_order", "prices_count", "thumb_preview")
    list_filter = ("is_active", "show_on_home", "category")
    search_fields = ("name", "name_en", "slug")
    list_editable = ("is_active", "show_on_home", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("thumb_preview",)
    inlines = [PriceInline]
    fieldsets = (
        (None, {
            "fields": ("category", "name", "name_en", "slug", "is_active", "show_on_home", "sort_order"),
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
            return format_html('<img src="{}" alt="" class="admin-detail-thumb">', obj.image.url)
        return "—"

    @admin.display(description=_("Позицій"))
    def prices_count(self, obj: Service) -> int:
        return obj.prices.count()


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


@admin.register(ProductSerial)
class ProductSerialAdmin(ModelAdmin):
    list_display = (
        "serial_number",
        "product_name",
        "product_code",
        "articul",
        "sale_document",
        "sale_date",
        "warranty_until",
        "source",
        "updated_at",
    )
    list_filter = ("source",)
    search_fields = ("serial_number", "product_name", "product_code", "articul", "sale_document")
    autocomplete_fields = ("product",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("serial_number", "product", "source")}),
        (_("Товар і продаж"), {
            "fields": (
                "product_name",
                "product_code",
                "articul",
                "sale_document",
                "sale_date",
                "warranty_until",
                "warranty_months",
                "brain_order_id",
            ),
        }),
        (_("Інше"), {"fields": ("notes", "created_at", "updated_at")}),
    )


@admin.register(WarrantyClaim)
class WarrantyClaimAdmin(ModelAdmin):
    list_display = (
        "rma_number",
        "serial_number",
        "product_name",
        "status",
        "is_under_warranty",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "is_under_warranty", "delivery_service")
    search_fields = ("rma_number", "serial_number", "product_name", "client_name", "client_phone")
    autocomplete_fields = ("product", "created_by", "product_serial")
    readonly_fields = ("created_at", "updated_at", "submitted_at")
    date_hierarchy = "created_at"
    fieldsets = (
        (_("RMA"), {"fields": ("rma_number", "status", "submitted_at")}),
        (_("Серійний номер"), {
            "fields": ("serial_number", "without_serial_number", "product_serial"),
        }),
        (_("Товар"), {
            "fields": (
                "product",
                "product_name",
                "product_code",
                "articul",
                "sale_document",
                "sale_date",
                "warranty_until",
                "is_under_warranty",
            ),
        }),
        (_("Дефект"), {"fields": ("defect_description", "comment")}),
        (_("Клієнт¹"), {
            "fields": ("client_name", "client_phone", "client_email", "client_address"),
        }),
        (_("Доставка²"), {
            "fields": ("delivery_service", "waybill_number", "waybill_date"),
        }),
        (_("Службове"), {"fields": ("created_by", "created_at", "updated_at")}),
    )
