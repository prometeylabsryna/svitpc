from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin_mixins import OptimizedAdminMixin

from .models import Address, Customer


class AddressInline(TabularInline):
    model = Address
    extra = 0
    fields = ("label", "city", "delivery_type", "warehouse", "is_default")


class TelegramBroadcastForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    telegram_text = forms.CharField(
        label=_("Текст повідомлення"),
        widget=forms.Textarea(attrs={"rows": 5}),
    )


@admin.register(Customer)
class CustomerAdmin(OptimizedAdminMixin, UserAdmin, ModelAdmin):
    list_display = ("email", "first_name", "last_name", "phone", "bonus_balance", "is_active", "date_joined")
    list_filter = ("is_active", "is_staff", "consent_email", "consent_sms")
    search_fields = ("email", "first_name", "last_name", "phone")
    ordering = ("-date_joined",)
    inlines = [AddressInline]
    actions = ["send_telegram_message"]
    readonly_fields = ("bonus_balance", "last_login", "date_joined")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Особиста інформація"), {"fields": ("first_name", "last_name", "phone", "birth_date")}),
        (_("Бонуси та підписки"), {"fields": ("bonus_balance", "consent_email", "consent_sms")}),
        (_("Месенджери"), {"fields": ("telegram_chat_id", "viber_id")}),
        (_("Права доступу"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Дати"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "phone", "password1", "password2"),
        }),
    )

    class Media:
        css = {"all": ("css/admin_extra.css",)}

    @admin.action(description=_("Надіслати Telegram-повідомлення"))
    def send_telegram_message(self, request, queryset):
        selected_pks = request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME)
        if "apply" in request.POST:
            form = TelegramBroadcastForm(request.POST)
            if form.is_valid():
                queryset = Customer.objects.filter(pk__in=form.cleaned_data["_selected_action"])
            else:
                queryset = Customer.objects.filter(pk__in=selected_pks or queryset.values_list("pk", flat=True))
        else:
            form = TelegramBroadcastForm(
                initial={"_selected_action": selected_pks or list(queryset.values_list("pk", flat=True))},
            )

        if "apply" in request.POST and form.is_valid():
            import asyncio

            from apps.bots.telegram.bot import send_message

            message = form.cleaned_data["telegram_text"]
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
            self.message_user(
                request,
                _("Надіслано: %(sent)d. Без Telegram ID або з помилкою: %(skipped)d.") % {"sent": sent, "skipped": skipped},
            )
            return None

        return render(
            request,
            "admin/customers/send_telegram.html",
            {
                "form": form,
                "customers": queryset,
                "title": _("Надіслати Telegram-повідомлення"),
                **self.admin_site.each_context(request),
            },
        )


@admin.register(Address)
class AddressAdmin(OptimizedAdminMixin, ModelAdmin):
    list_display = ("customer", "city", "delivery_type", "warehouse", "is_default")
    search_fields = ("customer__email", "city", "warehouse")
    list_filter = ("delivery_type", "is_default")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("customer")
