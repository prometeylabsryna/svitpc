from datetime import date

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from .forms import AddressForm, CustomerLoginForm, CustomerProfileForm, CustomerRegistrationForm
from .models import Address


def register_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("customers:dashboard")
    form = CustomerRegistrationForm(request.POST or None)
    if form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, _("Реєстрація успішна! Ласкаво просимо!"))
        return redirect("customers:dashboard")
    return render(request, "customers/register.html", {"form": form, "today": date.today().isoformat()})


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("customers:dashboard")
    form = CustomerLoginForm(request, request.POST or None)
    if form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get("next", "customers:dashboard"))
    return render(request, "customers/login.html", {"form": form})


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("/")


@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
    return render(request, "customers/dashboard.html")


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    form = CustomerProfileForm(request.POST or None, instance=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, _("Профіль оновлено"))
        return redirect("customers:profile")
    return render(request, "customers/profile.html", {"form": form})


@login_required
def addresses_view(request: HttpRequest) -> HttpResponse:
    addresses = request.user.addresses.all()
    return render(request, "customers/addresses.html", {"addresses": addresses})


@login_required
def address_create_view(request: HttpRequest) -> HttpResponse:
    form = AddressForm(request.POST or None)
    if form.is_valid():
        address = form.save(commit=False)
        address.customer = request.user
        if address.is_default:
            request.user.addresses.filter(is_default=True).update(is_default=False)
        address.save()
        messages.success(request, _("Адресу додано"))
        return redirect("customers:addresses")
    return render(request, "customers/address_form.html", {"form": form})


@login_required
def address_delete_view(request: HttpRequest, pk: int) -> HttpResponse:
    address = get_object_or_404(Address, pk=pk, customer=request.user)
    address.delete()
    messages.success(request, _("Адресу видалено"))
    return redirect("customers:addresses")
