"""Admin registration for loyalty app: Coupon, BonusTransaction."""

from __future__ import annotations

import secrets
import string

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from apps.core.admin_mixins import OptimizedAdminMixin

from .forms import BonusAdjustmentForm
from .models import BonusTransaction, Coupon
from .services import LoyaltyError


def _generate_code(length: int = 10) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@admin.register(Coupon)
class CouponAdmin(OptimizedAdminMixin, ModelAdmin):
    list_display = ("code", "customer", "source", "discount_type", "discount_value", "used_count", "max_uses", "is_active", "valid_to")
    autocomplete_fields = ("customer",)
    list_filter = ("is_active", "discount_type")
    search_fields = ("code",)
    list_editable = ("is_active",)
    readonly_fields = ("used_count",)
    actions = ["activate", "deactivate", "reset_used_count"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("customer")

    @admin.action(description=_("Активувати обрані промокоди"))
    def activate(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, _("Активовано: %(n)d") % {"n": updated})

    @admin.action(description=_("Деактивувати обрані промокоди"))
    def deactivate(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _("Деактивовано: %(n)d") % {"n": updated})

    @admin.action(description=_("Скинути лічильник використань"))
    def reset_used_count(self, request, queryset):
        queryset.update(used_count=0)
        self.message_user(request, _("Лічильник скинуто"))


@admin.register(BonusTransaction)
class BonusTransactionAdmin(OptimizedAdminMixin, ModelAdmin):
    list_display = ("customer", "transaction_type", "amount", "balance_after", "description", "created_at")
    list_filter = ("transaction_type",)
    search_fields = ("customer__email", "customer__phone", "description")
    autocomplete_fields = ("customer",)
    readonly_fields = ("customer", "order", "transaction_type", "amount", "balance_after", "created_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("customer", "order")

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return [(None, {"fields": ("customer", "amount", "description")})]
        return [(None, {"fields": self.readonly_fields})]

    def get_form(self, request, obj=None, change=False, **kwargs):
        if obj is None:
            kwargs["form"] = BonusAdjustmentForm
        return super().get_form(request, obj, change=change, **kwargs)

    def save_model(self, request, obj, form, change) -> None:
        if change:
            return
        try:
            tx = form.save()
            obj.pk = tx.pk
        except LoyaltyError as exc:
            messages.error(request, exc.message)
            raise

    def has_add_permission(self, request) -> bool:
        return request.user.is_staff

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return request.user.is_superuser
