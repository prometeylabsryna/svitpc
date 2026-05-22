from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.widgets import CKEditor5Widget
from mptt.admin import DraggableMPTTAdmin
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from .models import (
    Attribute,
    AttributeGroup,
    Brand,
    Category,
    Filter,
    FilterGroup,
    MarkupRule,
    Product,
    ProductAttribute,
    ProductFilter,
    ProductImage,
    Redirect,
    SeoUrl,
)


class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 0
    fields = ("image", "image_url", "alt", "sort_order")


class ProductAttributeInline(TabularInline):
    model = ProductAttribute
    extra = 0
    fields = ("attribute", "value")
    autocomplete_fields = ["attribute"]


@admin.register(Brand)
class BrandAdmin(ModelAdmin):
    list_display = ("name", "slug", "oc_id")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = "__all__"
        widgets = {
            "description": CKEditor5Widget(config_name="default"),
            "description_uk": CKEditor5Widget(config_name="default"),
            "description_en": CKEditor5Widget(config_name="default"),
        }


@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin, ModelAdmin):
    form = CategoryAdminForm
    list_display = ("tree_actions", "indented_title", "slug", "is_active", "is_top", "product_count_display")
    list_filter = ("is_active", "is_top", "level")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("is_active", "is_top")
    actions = ["generate_ai_description"]

    @admin.display(description=_("Товарів"))
    def product_count_display(self, obj: Category) -> int:
        return obj.products.count()

    @admin.action(description=_("Згенерувати AI-опис категорій"))
    def generate_ai_description(self, request, queryset):
        from apps.ai.services.content import generate_category_description
        count = 0
        for cat in queryset:
            if generate_category_description(cat.pk):
                count += 1
        self.message_user(request, _(f"Описи згенеровано для {count} категорій"))


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ("name", "sku", "brand", "price", "stock", "is_visible", "is_new", "is_hit", "source", "thumb_preview")
    list_filter = ("source", "is_visible", "is_new", "is_hit", "brand")
    search_fields = ("name", "sku", "external_id", "slug")
    list_editable = ("is_visible", "is_new", "is_hit", "price")
    filter_horizontal = ("categories",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline, ProductAttributeInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "sku", "model", "external_id", "source", "brand", "categories")}),
        (_("Вміст"), {"fields": ("short_description", "description", "image", "image_url")}),
        (_("Ціни та залишки"), {"fields": ("price", "old_price", "purchase_price", "stock", "is_visible", "hide_if_out_of_stock")}),
        (_("Позначки"), {"fields": ("is_new", "is_hit", "sort_order")}),
        (_("SEO"), {"fields": ("seo_title", "seo_description"), "classes": ("collapse",)}),
    )
    actions = [
        "generate_seo_action",
        "generate_description_action",
        "generate_short_description_action",
        "enhance_characteristics_action",
        "mark_as_new",
        "mark_as_hit",
        "brain_sync_incremental",
        "brain_sync_prices_stock",
        "brain_enable_hide_out_of_stock",
    ]

    @admin.display(description=_("Фото"))
    def thumb_preview(self, obj: Product) -> str:
        url = obj.main_image_url
        if url:
            return format_html('<img src="{}" width="40" height="40" style="object-fit:contain">', url)
        return "—"

    @admin.action(description=_("Згенерувати SEO (AI)"))
    def generate_seo_action(self, request, queryset):
        from apps.ai.services.content import generate_product_seo_bulk

        generate_product_seo_bulk.delay(list(queryset.values_list("pk", flat=True)))
        self.message_user(request, _("SEO-генерацію поставлено в чергу"))

    @admin.action(description=_("Згенерувати повні описи (AI)"))
    def generate_description_action(self, request, queryset):
        from apps.ai.services.content import generate_description_bulk

        generate_description_bulk.delay(list(queryset.values_list("pk", flat=True)))
        self.message_user(request, _("Генерацію описів поставлено в чергу"))

    @admin.action(description=_("Згенерувати короткі описи (AI)"))
    def generate_short_description_action(self, request, queryset):
        from apps.ai.services.content import generate_short_description_bulk

        generate_short_description_bulk.delay(list(queryset.values_list("pk", flat=True)))
        self.message_user(request, _("Генерацію коротких описів поставлено в чергу"))

    @admin.action(description=_("Покращити характеристики (AI)"))
    def enhance_characteristics_action(self, request, queryset):
        from apps.ai.services.content import enhance_characteristics_bulk

        enhance_characteristics_bulk.delay(list(queryset.values_list("pk", flat=True)))
        self.message_user(request, _("Покращення характеристик поставлено в чергу"))

    @admin.action(description=_("Позначити Новинками"))
    def mark_as_new(self, request, queryset):
        queryset.update(is_new=True)

    @admin.action(description=_("Позначити Хітами"))
    def mark_as_hit(self, request, queryset):
        queryset.update(is_hit=True)

    @admin.action(description=_("Brain: синхронізувати (ціни, залишки, фото, опції)"))
    def brain_sync_incremental(self, request, queryset):
        from apps.integrations.brain.tasks import sync_all_incremental

        sync_all_incremental.delay()
        self.message_user(request, _("Повну інкрементальну синхронізацію Brain поставлено в чергу Celery"))

    @admin.action(description=_("Brain: оновити ціни та залишки"))
    def brain_sync_prices_stock(self, request, queryset):
        from apps.integrations.brain.tasks import sync_prices, sync_stock

        sync_prices.delay()
        sync_stock.delay()
        self.message_user(request, _("Оновлення цін і залишків Brain поставлено в чергу"))

    @admin.action(description=_("Brain: приховувати без залишку"))
    def brain_enable_hide_out_of_stock(self, request, queryset):
        from apps.integrations.brain.tasks import apply_hide_out_of_stock_policy

        qs = queryset.filter(source="brain")
        updated = qs.update(hide_if_out_of_stock=True)
        apply_hide_out_of_stock_policy.delay()
        self.message_user(request, _(f"Увімкнено приховування для {updated} товарів Brain; видимість оновлюється в черзі"))


@admin.register(AttributeGroup)
class AttributeGroupAdmin(ModelAdmin):
    list_display = ("name", "sort_order")
    search_fields = ("name",)


@admin.register(Attribute)
class AttributeAdmin(ModelAdmin):
    list_display = ("name", "group", "sort_order")
    list_filter = ("group",)
    search_fields = ("name",)


@admin.register(FilterGroup)
class FilterGroupAdmin(ModelAdmin):
    list_display = ("name", "sort_order")
    search_fields = ("name",)


@admin.register(Filter)
class FilterAdmin(ModelAdmin):
    list_display = ("name", "group", "sort_order")
    list_filter = ("group",)
    search_fields = ("name",)


@admin.register(MarkupRule)
class MarkupRuleAdmin(ModelAdmin):
    list_display = ("name", "brand", "category", "markup_percent", "priority", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Redirect)
class RedirectAdmin(ModelAdmin):
    list_display = ("old_path", "new_path", "status_code", "is_active")
    list_filter = ("status_code", "is_active")
    search_fields = ("old_path", "new_path")
    list_editable = ("is_active",)


@admin.register(SeoUrl)
class SeoUrlAdmin(ModelAdmin):
    list_display = ("query", "keyword", "language_code")
    search_fields = ("query", "keyword")
    list_filter = ("language_code",)
