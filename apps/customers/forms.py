from datetime import date

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import Address, Customer


class CustomerRegistrationForm(UserCreationForm):
    first_name = forms.CharField(label=_("Ім'я"), max_length=100)
    last_name = forms.CharField(label=_("Прізвище"), max_length=100, required=False)
    phone = forms.CharField(label=_("Телефон"), max_length=20, min_length=10)
    birth_date = forms.DateField(
        label=_("Дата народження"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        hint = _("Мінімум 8 символів.")
        self.fields["password1"].help_text = hint
        for name in ("password1", "password2"):
            self.fields[name].widget.attrs.setdefault("minlength", "8")
            self.fields[name].widget.attrs.setdefault("autocomplete", "new-password")

    def clean_phone(self) -> str:
        from apps.notifications.phone import InvalidPhoneError, format_ua_phone_display

        phone = self.cleaned_data["phone"].strip()
        try:
            return format_ua_phone_display(phone)
        except InvalidPhoneError:
            raise forms.ValidationError(_("Введіть коректний номер телефону.")) from None

    def clean_birth_date(self) -> date:
        birth_date = self.cleaned_data["birth_date"]
        if birth_date > date.today():
            raise forms.ValidationError(_("Дата народження не може бути в майбутньому."))
        return birth_date

    class Meta(UserCreationForm.Meta):
        model = Customer
        fields = ("email", "first_name", "last_name", "phone", "birth_date")


class CustomerLoginForm(AuthenticationForm):
    username = forms.CharField(
        label=_("Email"),
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
        error_messages={"required": _("Введіть email.")},
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["password"].error_messages["required"] = _("Введіть пароль.")

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

    def clean_phone(self) -> str:
        from apps.notifications.phone import InvalidPhoneError, format_ua_phone_display

        phone = self.cleaned_data.get("phone", "").strip()
        if not phone:
            return phone
        try:
            return format_ua_phone_display(phone)
        except InvalidPhoneError:
            raise forms.ValidationError(_("Введіть коректний номер телефону.")) from None


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ("label", "first_name", "last_name", "phone", "city", "city_ref", "delivery_type", "warehouse", "warehouse_ref", "is_default")
        widgets = {"city_ref": forms.HiddenInput(), "warehouse_ref": forms.HiddenInput()}
