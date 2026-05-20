"""Admin registration for loyalty app: Coupon, BonusTransaction."""

from __future__ import annotations

import secrets
import string

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import BonusTransaction, Coupon


def _generate_code(length: int = 10) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@admin.register(Coupon)
class CouponAdmin(ModelAdmin):
    list_display = ("code", "discount_type", "discount_value", "used_count", "max_uses", "is_active", "valid_to")
    list_filter = ("is_active", "discount_type")
    search_fields = ("code",)
    list_editable = ("is_active",)
    readonly_fields = ("used_count",)
    date_hierarchy = "valid_from"
    actions = ["activate", "deactivate", "generate_codes"]

    @admin.action(description=_("Активувати обрані промокоди"))
    def activate(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, _("Активовано: %(n)d") % {"n": updated})

    @admin.action(description=_("Деактивувати обрані промокоди"))
    def deactivate(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _("Деактивовано: %(n)d") % {"n": updated})

    @admin.action(description=_("Скинути лічильник використань"))
    def generate_codes(self, request, queryset):
        queryset.update(used_count=0)
        self.message_user(request, _("Лічильник скинуто"))


@admin.register(BonusTransaction)
class BonusTransactionAdmin(ModelAdmin):
    list_display = ("customer", "transaction_type", "amount", "balance_after", "description", "created_at")
    list_filter = ("transaction_type",)
    search_fields = ("customer__email", "customer__phone", "description")
    date_hierarchy = "created_at"
    readonly_fields = ("customer", "order", "transaction_type", "amount", "balance_after", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
