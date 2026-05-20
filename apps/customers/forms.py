from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import Address, Customer


class CustomerRegistrationForm(UserCreationForm):
    first_name = forms.CharField(label=_("Ім'я"), max_length=100)
    last_name = forms.CharField(label=_("Прізвище"), max_length=100, required=False)
    phone = forms.CharField(label=_("Телефон"), max_length=20, required=False)
    birth_date = forms.DateField(
        label=_("Дата народження"),
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
    )

    class Meta(UserCreationForm.Meta):
        model = Customer
        fields = ("email", "first_name", "last_name", "phone", "birth_date")


class CustomerLoginForm(AuthenticationForm):
    username = forms.EmailField(label=_("Email"), widget=forms.EmailInput(attrs={"autofocus": True}))

    def clean(self) -> dict:
        email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if email and password:
            self.user_cache = authenticate(self.request, username=email, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(_("Невірний email або пароль."))
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ("first_name", "last_name", "phone", "birth_date", "consent_email", "consent_sms")
        widgets = {"birth_date": forms.DateInput(attrs={"type": "date"})}


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ("label", "first_name", "last_name", "phone", "city", "city_ref", "delivery_type", "warehouse", "warehouse_ref", "is_default")
        widgets = {"city_ref": forms.HiddenInput(), "warehouse_ref": forms.HiddenInput()}
