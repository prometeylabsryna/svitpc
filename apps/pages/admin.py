from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import InfoPage


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
