from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import Review


@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ("author_name", "product", "rating", "is_approved", "created_at")
    list_filter = ("is_approved", "rating")
    search_fields = ("author_name", "product__name_uk", "product__name_en", "text")
    list_editable = ("is_approved",)
    date_hierarchy = "created_at"
    readonly_fields = ("product", "customer", "author_name", "rating", "text", "created_at")
    actions = ["approve_selected", "reject_selected"]

    @admin.action(description=_("✅ Схвалити відгуки"))
    def approve_selected(self, request, queryset):
        queryset.update(is_approved=True)

    @admin.action(description=_("🚫 Відхилити відгуки"))
    def reject_selected(self, request, queryset):
        queryset.update(is_approved=False)
