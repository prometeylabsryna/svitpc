"""Forms for warranty claims."""

from __future__ import annotations

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .serial_lookup import normalize_serial
from .warranty_models import WarrantyClaim


class WarrantyClaimForm(forms.ModelForm):
    action = forms.ChoiceField(
        choices=[("save", _("Зберегти")), ("submit", _("Відправити"))],
        required=False,
        widget=forms.HiddenInput,
    )

    class Meta:
        model = WarrantyClaim
        fields = [
            "serial_number",
            "without_serial_number",
            "product",
            "product_name",
            "product_code",
            "articul",
            "sale_document",
            "sale_date",
            "warranty_until",
            "defect_description",
            "client_name",
            "client_phone",
            "client_email",
            "client_address",
            "delivery_service",
            "waybill_number",
            "waybill_date",
            "comment",
        ]
        widgets = {
            "sale_date": forms.DateInput(attrs={"type": "date"}),
            "warranty_until": forms.DateInput(attrs={"type": "date", "readonly": "readonly"}),
            "waybill_date": forms.DateInput(attrs={"type": "date"}),
            "defect_description": forms.Textarea(attrs={"rows": 3, "maxlength": "60"}),
            "comment": forms.Textarea(attrs={"rows": 4, "maxlength": "250"}),
            "product": forms.HiddenInput(),
        }

    def clean_serial_number(self) -> str:
        value = self.cleaned_data.get("serial_number", "")
        return normalize_serial(value) if value else ""

    def clean(self) -> dict:
        cleaned = super().clean()
        without_sn = cleaned.get("without_serial_number")
        serial = cleaned.get("serial_number", "")
        product_name = (cleaned.get("product_name") or "").strip()
        defect = (cleaned.get("defect_description") or "").strip()

        if not without_sn and not serial:
            self.add_error("serial_number", _("Вкажіть серійний номер або позначте «Без серійного номера»."))

        if not product_name:
            self.add_error("product_name", _("Оберіть або вкажіть товар."))

        if not defect:
            self.add_error("defect_description", _("Опишіть дефект."))

        client_fields = ("client_name", "client_phone", "client_email", "client_address")
        delivery_fields = ("delivery_service", "waybill_number", "waybill_date")
        if any((cleaned.get(f) or "").strip() for f in client_fields):
            for field in client_fields:
                if not (cleaned.get(field) or "").strip():
                    self.add_error(field, _("Заповніть усі поля клієнта¹."))
        if any((cleaned.get(f) or "").strip() for f in delivery_fields):
            for field in delivery_fields:
                if field == "waybill_date":
                    if cleaned.get(field) is None:
                        self.add_error(field, _("Заповніть усі поля доставки²."))
                elif not (cleaned.get(field) or "").strip():
                    self.add_error(field, _("Заповніть усі поля доставки²."))

        warranty_until = cleaned.get("warranty_until")
        if warranty_until:
            today = timezone.localdate()
            cleaned["is_under_warranty"] = warranty_until >= today
        return cleaned
