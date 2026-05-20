from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Order, OrderHistory, OrderItem, OrderStatus


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    fields = ("product", "name", "sku", "price", "qty")
    readonly_fields = ("product",)


class OrderHistoryInline(TabularInline):
    model = OrderHistory
    extra = 1
    fields = ("status", "comment", "notify_customer")


@admin.register(OrderStatus)
class OrderStatusAdmin(ModelAdmin):
    list_display = ("name", "color", "sort_order", "notify_customer")


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ("pk", "first_name", "last_name", "phone", "status", "total", "is_paid", "delivery_type", "ttn", "up_barcode", "created_at")
    list_filter = ("status", "is_paid", "delivery_type", "payment_method")
    search_fields = ("first_name", "last_name", "phone", "email", "ttn")
    list_editable = ("is_paid",)
    inlines = [OrderItemInline, OrderHistoryInline]
    readonly_fields = ("created_at", "updated_at", "payment_id", "fiscal_check_url")
    fieldsets = (
        ("Клієнт", {"fields": ("customer", "first_name", "last_name", "email", "phone", "comment")}),
        ("Доставка", {"fields": ("delivery_type", "city", "warehouse", "postcode", "ttn", "up_barcode")}),
        ("Оплата", {"fields": ("payment_method", "is_paid", "payment_id", "total", "delivery_cost", "discount", "bonus_used")}),
        ("Фіскалізація", {"fields": ("fiscal_check_url",)}),
        ("Статус", {"fields": ("status",)}),
        ("Системне", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    actions = ["create_ttn_action", "create_up_shipment_action", "send_status_notification", "fiscalize_orders_action"]

    @admin.action(description="Створити ТТН (Нова Пошта)")
    def create_ttn_action(self, request, queryset):
        from apps.shipping.tasks import create_ttn_for_order
        count = 0
        for order in queryset.filter(delivery_type="nova_poshta", ttn=""):
            create_ttn_for_order.delay(order.pk)
            count += 1
        self.message_user(request, f"ТТН поставлено в чергу: {count} замовлень")

    @admin.action(description="Створити відправлення (УкрПошта)")
    def create_up_shipment_action(self, request, queryset):
        from apps.integrations.ukrposhta.tasks import create_up_shipment_for_order
        count = 0
        for order in queryset.filter(delivery_type="ukrposhta", up_barcode=""):
            create_up_shipment_for_order.delay(order.pk)
            count += 1
        self.message_user(request, f"Відправлення УкрПошта поставлено в чергу: {count} замовлень")

    @admin.action(description="Надіслати сповіщення про статус")
    def send_status_notification(self, request, queryset):
        from apps.notifications.tasks import notify_order_status
        for order in queryset:
            notify_order_status.delay(order.pk)

    @admin.action(description="Фіскалізувати вибрані замовлення (Вчасно.Каса)")
    def fiscalize_orders_action(self, request, queryset):
        from apps.integrations.vchasnokasa.tasks import fiscalize_payment
        count = 0
        for order in queryset.filter(is_paid=True, fiscal_check_url=""):
            fiscalize_payment.delay(order.pk)
            count += 1
        self.message_user(request, f"Фіскалізацію поставлено в чергу: {count} замовлень")
