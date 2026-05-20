from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from .models import Address, Customer


class AddressInline(TabularInline):
    model = Address
    extra = 0
    fields = ("label", "city", "delivery_type", "warehouse", "is_default")


@admin.register(Customer)
class CustomerAdmin(UserAdmin, ModelAdmin):
    list_display = ("email", "first_name", "last_name", "phone", "bonus_balance", "is_active", "date_joined")
    list_filter = ("is_active", "is_staff", "consent_email", "consent_sms")
    search_fields = ("email", "first_name", "last_name", "phone")
    ordering = ("-date_joined",)
    inlines = [AddressInline]
    actions = ["send_telegram_message"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Особиста інформація"), {"fields": ("first_name", "last_name", "phone", "birth_date")}),
        (_("Бонуси та підписки"), {"fields": ("bonus_balance", "consent_email", "consent_sms")}),
        (_("Месенджери"), {"fields": ("telegram_chat_id",)}),
        (_("Права доступу"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Дати"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "phone", "password1", "password2"),
        }),
    )

    @admin.action(description=_("Надіслати Telegram-повідомлення"))
    def send_telegram_message(self, request: HttpRequest, queryset) -> None:
        import asyncio
        from apps.bots.telegram.bot import send_message

        message = request.POST.get("telegram_text", "")
        if not message:
            self.message_user(request, _("Введіть текст у полі telegram_text."), level="error")
            return

        sent, skipped = 0, 0
        for customer in queryset:
            if customer.telegram_chat_id:
                try:
                    asyncio.run(send_message(customer.telegram_chat_id, message))
                    sent += 1
                except Exception:
                    skipped += 1
            else:
                skipped += 1

        self.message_user(request, _(f"Надіслано: {sent}. Без Telegram ID: {skipped}."))


@admin.register(Address)
class AddressAdmin(ModelAdmin):
    list_display = ("customer", "city", "delivery_type", "warehouse", "is_default")
    search_fields = ("customer__email", "city", "warehouse")
    list_filter = ("delivery_type", "is_default")
