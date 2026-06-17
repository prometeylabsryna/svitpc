"""Order admin and related forms."""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.orders.models import Order
from apps.orders.statuses import admin_status_queryset
from apps.shipping.validation import validate_checkout_step1


class OrderAdminForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = "__all__"
        widgets = {
            "city_ref": forms.HiddenInput(),
            "warehouse_ref": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].queryset = admin_status_queryset()
        self.fields["city"].widget.attrs.update(
            {
                "autocomplete": "off",
                "placeholder": _("Почніть вводити назву міста..."),
                "data-np-city-input": "1",
            }
        )
        self.fields["warehouse"].widget.attrs.update(
            {
                "autocomplete": "off",
                "placeholder": _("Оберіть відділення..."),
                "data-np-warehouse-input": "1",
            }
        )

    def clean(self):
        cleaned = super().clean()
        if not cleaned:
            return cleaned

        delivery_type = cleaned.get("delivery_type") or Order.DELIVERY_NP
        has_ttn = bool((self.instance.pk and self.instance.ttn) or cleaned.get("ttn"))

        if delivery_type == Order.DELIVERY_PICKUP:
            cleaned["city"] = ""
            cleaned["city_ref"] = ""
            cleaned["warehouse"] = ""
            cleaned["warehouse_ref"] = ""
            cleaned["postcode"] = ""
        elif delivery_type == Order.DELIVERY_UP:
            cleaned["warehouse"] = ""
            cleaned["warehouse_ref"] = ""
            cleaned["city_ref"] = ""
        elif delivery_type != Order.DELIVERY_NP:
            cleaned["city_ref"] = ""
            cleaned["warehouse_ref"] = ""

        if delivery_type == Order.DELIVERY_NP and has_ttn:
            return cleaned

        errors = validate_checkout_step1(
            {
                "first_name": cleaned.get("first_name", ""),
                "last_name": cleaned.get("last_name", ""),
                "phone": cleaned.get("phone", ""),
                "delivery_type": delivery_type,
                "city": cleaned.get("city", ""),
                "city_ref": cleaned.get("city_ref", ""),
                "warehouse_ref": cleaned.get("warehouse_ref", ""),
                "postcode": cleaned.get("postcode", ""),
            }
        )
        for msg in errors:
            lowered = str(msg).lower()
            if "списку" in lowered or ("місто" in lowered and "доставки" in lowered):
                self.add_error("city", msg)
            elif "відділення" in lowered:
                self.add_error("warehouse", msg)
            elif "індекс" in lowered:
                self.add_error("postcode", msg)
            elif "ім" in lowered:
                self.add_error("first_name", msg)
            elif "прізвище" in lowered:
                self.add_error("last_name", msg)
            elif "телефон" in lowered:
                self.add_error("phone", msg)
            else:
                self.add_error(None, msg)

        return cleaned
