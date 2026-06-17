from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from .forms import OrderAdminForm
from .models import Order, OrderItem, OrderStatus
from .statuses import admin_status_queryset


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    fields = ("product", "name", "sku", "price", "qty")
    readonly_fields = ("product",)


@admin.register(OrderStatus)
class OrderStatusAdmin(ModelAdmin):
    list_display = ("name", "name_en", "color", "sort_order", "is_completed")
    search_fields = ("name", "name_en")
    fieldsets = (
        (None, {"fields": ("name", "name_en", "color", "sort_order", "is_completed")}),
    )


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    form = OrderAdminForm
    list_display = ("pk", "first_name", "last_name", "phone", "status", "total", "is_paid", "delivery_type", "ttn", "created_at")
    list_filter = ("status", "is_paid", "delivery_type", "payment_method")
    search_fields = ("first_name", "last_name", "phone", "email", "ttn")
    list_editable = ("is_paid",)
    autocomplete_fields = ("customer", "coupon")
    inlines = [OrderItemInline]
    readonly_fields = ("created_at", "updated_at", "payment_id", "fiscal_check_url")
    fieldsets = (
        ("Клієнт", {"fields": ("customer", "first_name", "last_name", "email", "phone", "comment")}),
        (
            "Доставка",
            {
                "fields": (
                    "delivery_type",
                    "city",
                    "city_ref",
                    "warehouse",
                    "warehouse_ref",
                    "ttn",
                ),
            },
        ),
        ("Оплата", {"fields": ("payment_method", "is_paid", "payment_id", "total", "delivery_cost", "discount", "bonus_used", "coupon")}),
        ("Фіскалізація", {"fields": ("fiscal_check_url",)}),
        (_("Статус замовлення"), {"fields": ("status",)}),
        ("Системне", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    actions = ["create_ttn_action", "send_status_notification", "fiscalize_orders_action"]

    class Media:
        css = {"all": ("css/admin_extra.css",)}
        js = ("admin/js/order_np_delivery.js",)

    def save_model(self, request, obj, form, change):
        if not obj.status_id:
            default = admin_status_queryset().first()
            if default:
                obj.status = default
        super().save_model(request, obj, form, change)

        if obj.delivery_type != Order.DELIVERY_NP or obj.ttn:
            return

        from apps.shipping.dispatch import order_ready_for_shipment

        if not obj.city_ref or not obj.warehouse_ref:
            self.message_user(
                request,
                "Для ТТН оберіть місто і відділення з підказок (не просто текст).",
                level=messages.WARNING,
            )
            return

        if order_ready_for_shipment(obj):
            self.message_user(
                request,
                "ТТН поставлено в чергу. Оновіть сторінку через 5–10 секунд.",
                level=messages.INFO,
            )

    @admin.action(description="Створити ТТН (Нова Пошта)")
    def create_ttn_action(self, request, queryset):
        from apps.shipping.dispatch import order_ready_for_shipment
        from apps.shipping.tasks import create_ttn_for_order

        success = 0
        skipped: list[str] = []
        failed: list[str] = []

        for order in queryset.filter(delivery_type="nova_poshta", ttn=""):
            if not order.city_ref or not order.warehouse_ref:
                skipped.append(f"#{order.pk} — немає міста/відділення з підказок")
                continue
            if not order_ready_for_shipment(order):
                skipped.append(f"#{order.pk} — не оплачено (картка) або вже має ТТН")
                continue
            err = create_ttn_for_order(order.pk)
            order.refresh_from_db()
            if order.ttn:
                success += 1
            elif err:
                failed.append(f"#{order.pk}: {err}")
            else:
                failed.append(f"#{order.pk}: невідома помилка")

        parts: list[str] = []
        if success:
            parts.append(f"ТТН створено: {success}")
        if skipped:
            parts.append("пропущено: " + "; ".join(skipped))
        if failed:
            parts.append(
                f"помилка API для №: {', '.join(failed)} — перевірте NP_SENDER_* у .env і логи worker"
            )
        if not parts:
            parts.append("жодне замовлення не обрано")

        level = messages.ERROR if failed and not success else messages.WARNING if failed or skipped else messages.SUCCESS
        self.message_user(request, "ТТН: " + ". ".join(parts) + ".", level=level)

    @admin.action(description="Надіслати сповіщення про статус")
    def send_status_notification(self, request, queryset):
        from apps.notifications.tasks import notify_order_status
        for order in queryset:
            notify_order_status.delay(order.pk)

    @admin.action(description="Фіскалізувати вибрані замовлення (Вчасно.Каса)")
    def fiscalize_orders_action(self, request, queryset):
        from apps.integrations.vchasnokasa.client import VchasnoKasaClient

        client = VchasnoKasaClient()
        if not client.is_configured():
            self.message_user(
                request,
                "VCHASNO_CASHBOX_KEY не задано — додайте токен каси в .env і перезапустіть сервер (make run).",
                level=messages.ERROR,
            )
            return

        success = 0
        skipped_paid = 0
        skipped_check = 0
        failed: list[str] = []

        for order in queryset.select_related().prefetch_related("items"):
            if order.fiscal_check_url:
                skipped_check += 1
                continue
            if not order.is_paid:
                skipped_paid += 1
                continue
            url = client.create_receipt(order)
            if url:
                Order.objects.filter(pk=order.pk).update(fiscal_check_url=url)
                success += 1
            else:
                failed.append(str(order.pk))

        parts: list[str] = []
        if success:
            parts.append(f"чек створено: {success}")
        if skipped_paid:
            parts.append(
                f"пропущено (не оплачено): {skipped_paid} — увімкніть «Оплачено» і натисніть «Зберегти»"
            )
        if skipped_check:
            parts.append(f"пропущено (вже мають чек): {skipped_check}")
        if failed:
            parts.append(f"помилка API для №: {', '.join(failed)}")

        if not parts:
            parts.append("жодне замовлення не обрано")

        level = messages.ERROR if failed and not success else messages.WARNING if failed or skipped_paid else messages.SUCCESS
        self.message_user(request, "Фіскалізація: " + "; ".join(parts) + ".", level=level)
