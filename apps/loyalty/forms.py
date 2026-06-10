"""Admin forms for loyalty."""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import BonusTransaction


class BonusAdjustmentForm(forms.ModelForm):
    amount = forms.DecimalField(
        label=_("Зміна монет"),
        help_text=_("Додатне значення — нарахування, від'ємне — списання."),
        max_digits=10,
        decimal_places=2,
    )

    class Meta:
        model = BonusTransaction
        fields = ("customer", "amount", "description")
        labels = {
            "customer": _("Покупець"),
            "description": _("Опис"),
        }

    def save(self, commit=True):
        from .services import apply_bonus_adjustment

        return apply_bonus_adjustment(
            self.cleaned_data["customer"],
            self.cleaned_data["amount"],
            self.cleaned_data.get("description", ""),
        )
