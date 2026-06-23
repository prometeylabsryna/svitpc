from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from apps.core.admin_mixins import OptimizedAdminMixin

from .models import Review


@admin.register(Review)
class ReviewAdmin(OptimizedAdminMixin, ModelAdmin):
    list_display = ("author_name", "product", "rating", "is_approved", "created_at")
    list_filter = ("is_approved", "rating")
    search_fields = ("author_name", "product__name_uk", "product__name_en", "text")
    list_editable = ("is_approved",)
    readonly_fields = ("product", "customer", "author_name", "rating", "text", "created_at")
    actions = ["approve_selected", "reject_selected"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("product", "customer")

    def has_add_permission(self, request) -> bool:
        return False

    @admin.action(description=_("✅ Схвалити відгуки"))
    def approve_selected(self, request, queryset):
        queryset.update(is_approved=True)

    @admin.action(description=_("🚫 Відхилити відгуки"))
    def reject_selected(self, request, queryset):
        queryset.update(is_approved=False)
