from django import forms
from django.contrib import admin, messages
from django.db.models import Count
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.widgets import CKEditor5Widget
from modeltranslation.admin import TranslationTabularInline
from mptt.admin import DraggableMPTTAdmin
from unfold.admin import ModelAdmin, TabularInline

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
from .admin_category_tree import get_admin_category_tree_nodes
from .widgets import CategoryTreeWidget


class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 0
    fields = ("image", "image_url", "alt", "sort_order")


class ProductAttributeInlineForm(forms.ModelForm):
    """Keep existing attribute values when inline POST omits unchanged rows."""

    class Meta:
        model = ProductAttribute
        fields = "__all__"

    def full_clean(self) -> None:
        if self.is_bound and self.instance.pk:
            data = self.data.copy()
            for field_name in ("value_uk", "value"):
                key = self.add_prefix(field_name)
                if key in data and not str(data.get(key, "")).strip():
                    existing = getattr(self.instance, field_name, None) or self.instance.value
                    if existing:
                        data[key] = existing
            self.data = data
        super().full_clean()


class ProductAttributeInline(TranslationTabularInline, TabularInline):
    model = ProductAttribute
    form = ProductAttributeInlineForm
    extra = 0
    fields = ("attribute", "value")
    autocomplete_fields = ["attribute"]


class ProductFilterInline(TabularInline):
    model = ProductFilter
    extra = 0
    fields = ("filter",)
    autocomplete_fields = ("filter",)


class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = "__all__"
        widgets = {
            "description": CKEditor5Widget(config_name="default"),
            "description_en": CKEditor5Widget(config_name="default"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["categories"]
        field.queryset = Category.objects.filter(is_active=True).order_by("tree_id", "lft")
        field.widget = CategoryTreeWidget(nodes=get_admin_category_tree_nodes())


class BrandAdminForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = "__all__"
        widgets = {
            "description": CKEditor5Widget(config_name="default"),
            "description_en": CKEditor5Widget(config_name="default"),
        }


@admin.register(Brand)
class BrandAdmin(ModelAdmin):
    form = BrandAdminForm
    list_display = ("name", "slug", "oc_id")
    search_fields = ("name", "name_en", "slug")
    prepopulated_fields = {"slug": ("name",)}
    fields = ("name", "name_en", "slug", "logo", "description", "description_en", "sort_order", "oc_id")


class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = "__all__"
        widgets = {
            "description": CKEditor5Widget(config_name="default"),
            "description_en": CKEditor5Widget(config_name="default"),
        }


@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin, ModelAdmin):
    form = CategoryAdminForm
    list_display = ("tree_actions", "indented_title", "slug", "is_active", "is_top", "product_count_display")
    list_filter = ("is_active", "is_top", "level")
    search_fields = ("name", "name_en", "slug")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("is_active", "is_top")
    actions = ["generate_ai_description"]

    def label_from_instance(self, obj: Category) -> str:
        return obj.admin_path
    fieldsets = (
        (None, {"fields": ("parent", "name", "name_en", "slug", "is_active", "is_top", "sort_order")}),
        (_("Вміст"), {"fields": ("description", "description_en", "image", "icon")}),
        (_("SEO"), {
            "fields": ("seo_title", "seo_title_en", "seo_description", "seo_description_en"),
            "classes": ("collapse",),
        }),
        (_("Інтеграції"), {
            "fields": ("oc_id", "kancmaster_name"),
            "classes": ("collapse",),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_product_count=Count("products", distinct=True))

    @admin.display(description=_("Товарів"))
    def product_count_display(self, obj: Category) -> int:
        return getattr(obj, "_product_count", 0)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from .admin_category_tree import invalidate_admin_category_tree_cache

        invalidate_admin_category_tree_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        from .admin_category_tree import invalidate_admin_category_tree_cache

        invalidate_admin_category_tree_cache()

    @admin.action(description=_("Згенерувати AI-опис категорій"))
    def generate_ai_description(self, request, queryset):
        from apps.ai.services.content import generate_category_description
        from apps.ai.services.llm import is_llm_configured

        if not is_llm_configured():
            self.message_user(
                request,
                _("LLM_API_KEY не налаштовано в .env — додайте ключ OpenAI-сумісного API."),
                level=messages.ERROR,
            )
            return

        count = 0
        for cat in queryset:
            if generate_category_description(cat.pk):
                count += 1
        self.message_user(request, _(f"Описи згенеровано для {count} категорій"))


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    form = ProductAdminForm
    class Media:
        css = {"all": ("css/admin_extra.css",)}

    list_display = ("name", "sku", "brand", "price", "stock", "is_visible", "is_new", "is_hit", "source", "thumb_preview")
    list_filter = ("source", "is_visible", "is_new", "is_hit", "brand")
    search_fields = ("name", "name_uk", "name_en", "sku", "external_id", "slug")
    list_editable = ("is_visible", "is_new", "is_hit", "price")
    list_per_page = 50
    show_full_result_count = False
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("brand",)
    inlines = [ProductImageInline, ProductAttributeInline, ProductFilterInline]
    fieldsets = (
        (None, {"fields": ("name", "name_en", "slug", "sku", "model", "external_id", "source", "brand", "categories")}),
        (_("Вміст"), {
            "fields": (
                "short_description",
                "short_description_en",
                "description",
                "description_en",
                "image",
                "image_url",
            ),
        }),
        (_("Ціни та залишки"), {
            "fields": (
                "price",
                "old_price",
                "purchase_price",
                "stock",
                "is_visible",
                "hide_if_out_of_stock",
                "sale_end_date",
            ),
        }),
        (_("Позначки"), {"fields": ("is_new", "is_hit", "sort_order")}),
        (_("SEO"), {
            "fields": ("seo_title", "seo_title_en", "seo_description", "seo_description_en"),
            "classes": ("collapse",),
        }),
    )
    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("brand")
            .prefetch_related("images")
        )

    actions = [
        "generate_seo_action",
        "generate_description_action",
        "generate_short_description_action",
        "enhance_characteristics_action",
        "mark_as_new",
        "mark_as_hit",
        "set_sale_end_date_action",
        "clear_sale_end_date_action",
        "brain_sync_incremental",
        "brain_sync_prices_stock",
        "brain_enable_hide_out_of_stock",
    ]

    @admin.display(description=_("Фото"))
    def thumb_preview(self, obj: Product) -> str:
        url = obj.main_image_url
        if url:
            return format_html('<img src="{}" alt="" class="admin-list-thumb">', url)
        return "—"

    @admin.action(description=_("Згенерувати SEO (AI)"))
    def generate_seo_action(self, request, queryset):
        from apps.ai.services.content import generate_product_seo_bulk
        from apps.ai.services.llm import is_llm_configured

        if not is_llm_configured():
            self.message_user(
                request,
                _("LLM_API_KEY не налаштовано в .env — додайте ключ OpenAI-сумісного API."),
                level=messages.ERROR,
            )
            return

        generate_product_seo_bulk.delay(list(queryset.values_list("pk", flat=True)))
        self.message_user(request, _("SEO-генерацію поставлено в чергу"))

    @admin.action(description=_("Згенерувати повні описи (AI)"))
    def generate_description_action(self, request, queryset):
        from apps.ai.services.content import generate_description_bulk
        from apps.ai.services.llm import is_llm_configured

        if not is_llm_configured():
            self.message_user(
                request,
                _("LLM_API_KEY не налаштовано в .env — додайте ключ OpenAI-сумісного API."),
                level=messages.ERROR,
            )
            return

        generate_description_bulk.delay(list(queryset.values_list("pk", flat=True)))
        self.message_user(request, _("Генерацію описів поставлено в чергу"))

    @admin.action(description=_("Згенерувати короткі описи (AI)"))
    def generate_short_description_action(self, request, queryset):
        from apps.ai.services.content import generate_short_description_bulk
        from apps.ai.services.llm import is_llm_configured

        if not is_llm_configured():
            self.message_user(
                request,
                _("LLM_API_KEY не налаштовано в .env — додайте ключ OpenAI-сумісного API."),
                level=messages.ERROR,
            )
            return

        generate_short_description_bulk.delay(list(queryset.values_list("pk", flat=True)))
        self.message_user(request, _("Генерацію коротких описів поставлено в чергу"))

    @admin.action(description=_("Покращити характеристики (AI)"))
    def enhance_characteristics_action(self, request, queryset):
        from apps.ai.services.content import enhance_characteristics_bulk
        from apps.ai.services.llm import is_llm_configured

        if not is_llm_configured():
            self.message_user(
                request,
                _("LLM_API_KEY не налаштовано в .env — додайте ключ OpenAI-сумісного API."),
                level=messages.ERROR,
            )
            return

        enhance_characteristics_bulk.delay(list(queryset.values_list("pk", flat=True)))
        self.message_user(request, _("Покращення характеристик поставлено в чергу"))

    @admin.action(description=_("Позначити Новинками"))
    def mark_as_new(self, request, queryset):
        queryset.update(is_new=True)

    @admin.action(description=_("Позначити Хітами"))
    def mark_as_hit(self, request, queryset):
        queryset.update(is_hit=True)

    @admin.action(description=_("⏱ Встановити таймер акції (масово)"))
    def set_sale_end_date_action(self, request, queryset):
        selected_ids = list(queryset.values_list("id", flat=True))
        if "apply" in request.POST:
            raw = request.POST.get("sale_end_date", "").strip()
            if raw:
                dt = parse_datetime(raw)
                if dt and timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                if dt:
                    products = list(queryset)
                    for product in products:
                        product.sale_end_date = dt
                        product.save(update_fields=["sale_end_date"])
                    self.message_user(
                        request,
                        _("Таймер акції встановлено для %(n)d товарів.") % {"n": len(products)},
                        messages.SUCCESS,
                    )
                    return redirect("admin:catalog_product_changelist")
            self.message_user(request, _("Вкажіть коректну дату та час."), messages.ERROR)

        context = {
            **self.admin_site.each_context(request),
            "title": _("Встановити таймер акції"),
            "queryset": queryset,
            "selected_ids": selected_ids,
            "action": "set_sale_end_date_action",
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
            "opts": self.model._meta,
        }
        return render(request, "admin/catalog/product/set_sale_end_date.html", context)

    @admin.action(description=_("✖ Зняти таймер акції (масово)"))
    def clear_sale_end_date_action(self, request, queryset):
        products = list(queryset)
        for product in products:
            product.sale_end_date = None
            product.save(update_fields=["sale_end_date"])
        self.message_user(
            request,
            _("Таймер знято з %(n)d товарів.") % {"n": len(products)},
            messages.SUCCESS,
        )

    @admin.action(description=_("Brain: повна інкрементальна синхронізація (весь каталог)"))
    def brain_sync_incremental(self, request, queryset):
        from apps.integrations.brain.tasks import sync_all_incremental

        brain_count = queryset.filter(source=Product.SOURCE_BRAIN).count()
        sync_all_incremental.delay()
        self.message_user(
            request,
            _(
                "Повну інкрементальну синхронізацію Brain поставлено в чергу. "
                "Задача оновлює весь каталог Brain (не лише вибрані рядки). "
                "У виборі товарів Brain: %(count)d."
            )
            % {"count": brain_count},
        )

    @admin.action(description=_("Brain: оновити ціни та залишки (весь каталог)"))
    def brain_sync_prices_stock(self, request, queryset):
        from apps.integrations.brain.tasks import sync_prices, sync_stock

        brain_count = queryset.filter(source=Product.SOURCE_BRAIN).count()
        sync_prices.delay()
        sync_stock.delay()
        self.message_user(
            request,
            _(
                "Оновлення цін і залишків Brain поставлено в чергу для всього каталогу. "
                "У виборі товарів Brain: %(count)d."
            )
            % {"count": brain_count},
        )

    @admin.action(description=_("Brain: приховувати без залишку (лише вибрані)"))
    def brain_enable_hide_out_of_stock(self, request, queryset):
        from apps.integrations.brain.tasks import apply_hide_out_of_stock_policy

        qs = queryset.filter(source=Product.SOURCE_BRAIN)
        if not qs.exists():
            self.message_user(
                request,
                _("Серед вибраних немає товарів Brain — оберіть товари з джерелом Brain."),
                level=messages.WARNING,
            )
            return
        updated = qs.update(hide_if_out_of_stock=True)
        apply_hide_out_of_stock_policy.delay()
        self.message_user(request, _(f"Увімкнено приховування для {updated} товарів Brain; видимість оновлюється в черзі"))


@admin.register(AttributeGroup)
class AttributeGroupAdmin(ModelAdmin):
    list_display = ("name", "sort_order")
    search_fields = ("name", "name_en")
    fields = ("name", "name_en", "sort_order", "oc_id")


@admin.register(Attribute)
class AttributeAdmin(ModelAdmin):
    list_display = ("name", "group", "sort_order")
    list_filter = ("group",)
    search_fields = ("name", "name_en")
    fields = ("group", "name", "name_en", "sort_order", "oc_id")


@admin.register(FilterGroup)
class FilterGroupAdmin(ModelAdmin):
    list_display = ("name", "sort_order", "filter_count_display", "product_link_count_display", "is_brand")
    list_filter = ("is_brand",)
    search_fields = ("name", "name_en")
    fields = ("name", "name_en", "sort_order", "is_brand", "oc_id")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _filter_count=Count("filters", distinct=True),
            _product_link_count=Count("filters__productfilter", distinct=True),
        )

    @admin.display(description=_("Значень"))
    def filter_count_display(self, obj: FilterGroup) -> int:
        return getattr(obj, "_filter_count", 0)

    @admin.display(description=_("Товарів"))
    def product_link_count_display(self, obj: FilterGroup) -> int:
        return getattr(obj, "_product_link_count", 0)


@admin.register(Filter)
class FilterAdmin(ModelAdmin):
    list_display = ("name", "group", "sort_order", "product_link_count_display")
    list_filter = ("group",)
    search_fields = ("name", "name_en", "group__name")
    fields = ("group", "name", "name_en", "sort_order", "oc_id")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_product_link_count=Count("productfilter", distinct=True))

    @admin.display(description=_("Товарів"))
    def product_link_count_display(self, obj: Filter) -> int:
        return getattr(obj, "_product_link_count", 0)


@admin.register(MarkupRule)
class MarkupRuleAdmin(ModelAdmin):
    list_display = ("name", "brand", "category", "markup_percent", "priority", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    autocomplete_fields = ("brand", "category")


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
