from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import PushSubscription


@admin.register(PushSubscription)
class PushSubscriptionAdmin(ModelAdmin):
    list_display = ("customer", "endpoint_short", "created_at")
    search_fields = ("customer__email", "customer__phone", "endpoint")
    date_hierarchy = "created_at"
    readonly_fields = ("customer", "endpoint", "p256dh", "auth", "created_at")

    def has_add_permission(self, request) -> bool:
        return False

    @admin.display(description=_("Endpoint"))
    def endpoint_short(self, obj: PushSubscription) -> str:
        return obj.endpoint[:60] + "…" if len(obj.endpoint) > 60 else obj.endpoint
