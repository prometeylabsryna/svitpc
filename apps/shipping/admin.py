from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import NovaPoshtaCity, NovaPoshtaWarehouse


class NovaPoshtaWarehouseInline(admin.TabularInline):
    model = NovaPoshtaWarehouse
    extra = 0
    fields = ("number", "name", "ref", "type")
    readonly_fields = ("ref",)
    show_change_link = True


@admin.register(NovaPoshtaCity)
class NovaPoshtaCityAdmin(ModelAdmin):
    list_display = ("name", "area", "ref", "updated_at")
    search_fields = ("name", "ref")
    list_filter = ("area",)
    readonly_fields = ("ref", "updated_at")
    inlines = [NovaPoshtaWarehouseInline]


@admin.register(NovaPoshtaWarehouse)
class NovaPoshtaWarehouseAdmin(ModelAdmin):
    list_display = ("city", "number", "name", "type", "ref")
    search_fields = ("name", "number", "ref", "city__name")
    list_filter = ("type",)
    readonly_fields = ("ref",)
    list_select_related = ("city",)
