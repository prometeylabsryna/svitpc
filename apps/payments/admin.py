from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from apps.core.admin_mixins import OptimizedAdminMixin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(OptimizedAdminMixin, ModelAdmin):
    list_display = ("pk", "order", "provider", "status", "amount", "currency", "transaction_id", "created_at")
    list_filter = ("status", "provider", "currency")
    search_fields = ("transaction_id", "idempotency_key", "order__pk")
    date_hierarchy = "created_at"
    readonly_fields = (
        "order", "provider", "status", "amount", "currency",
        "transaction_id", "idempotency_key", "raw_response",
        "created_at", "updated_at",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("order")

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return request.user.is_superuser
