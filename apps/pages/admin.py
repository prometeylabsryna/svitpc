from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import InfoPage, ReturnRequest


@admin.register(ReturnRequest)
class ReturnRequestAdmin(ModelAdmin):
    list_display = (
        "full_name",
        "order_number",
        "phone",
        "reason",
        "status",
        "created_at",
    )
    list_filter = ("status", "reason", "created_at")
    search_fields = ("full_name", "order_number", "phone")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {
            "fields": (
                "full_name",
                "order_number",
                "phone",
                "reason",
                "description",
                "photo",
                "status",
            ),
        }),
        (_("Службове"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(InfoPage)
class InfoPageAdmin(ModelAdmin):
    list_display = ("title", "slug", "is_active", "sort_order", "updated_at")
    list_editable = ("is_active", "sort_order")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "slug")
    fieldsets = (
        (None, {
            "fields": ("title", "title_en", "slug", "is_active", "sort_order"),
        }),
        (_("Вміст"), {
            "fields": ("content", "content_en"),
        }),
        (_("SEO"), {
            "fields": ("seo_title", "seo_description"),
            "classes": ("collapse",),
        }),
    )
