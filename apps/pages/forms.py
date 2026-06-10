"""Forms for public info pages."""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import ReturnRequest

MAX_PHOTO_SIZE = 5 * 1024 * 1024
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ReturnRequestForm(forms.ModelForm):
    class Meta:
        model = ReturnRequest
        fields = [
            "full_name",
            "order_number",
            "phone",
            "reason",
            "description",
            "photo",
        ]
        widgets = {
            "full_name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "autocomplete": "name",
                    "placeholder": _("Прізвище Ім'я По батькові"),
                }
            ),
            "order_number": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": _("Наприклад, 12345"),
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "type": "tel",
                    "autocomplete": "tel",
                    "placeholder": "+38 (0__) ___-__-__",
                }
            ),
            "reason": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 4,
                    "placeholder": _("Опишіть ситуацію детальніше"),
                }
            ),
            "photo": forms.FileInput(
                attrs={
                    "class": "returns-form__file-input",
                    "accept": "image/png,image/jpeg,image/webp",
                    "data-returns-file-input": "",
                }
            ),
        }

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if not photo:
            return photo
        if photo.size > MAX_PHOTO_SIZE:
            raise ValidationError(_("Файл занадто великий. Максимальний розмір — 5 МБ."))
        content_type = getattr(photo, "content_type", "") or ""
        if content_type and content_type not in ALLOWED_PHOTO_TYPES:
            raise ValidationError(_("Дозволені лише зображення PNG, JPG або WEBP."))
        return photo
