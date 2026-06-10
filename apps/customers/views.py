import json
from datetime import date

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods, require_POST

from apps.catalog.models import Product
from apps.reviews.views import _reviews_context

from .forms import AddressForm, CustomerLoginForm, CustomerProfileForm, CustomerRegistrationForm
from .models import Address, Customer
from .redirects import htmx_redirect_url, safe_next_url
from apps.core.svitik import svitik_event

from .utils import customer_display_name, customer_welcome_message

_CUSTOMER_AUTH_BACKEND = "apps.customers.backends.CustomerModelBackend"


def _hx_trigger(response: HttpResponse, payload: dict) -> HttpResponse:
    response["HX-Trigger"] = json.dumps(payload, ensure_ascii=True)
    return response


def _product_from_request(request: HttpRequest) -> Product | None:
    raw = request.GET.get("product_id") or request.POST.get("product_id")
    if not raw:
        return None
    try:
        return Product.objects.filter(pk=int(raw), is_visible=True).first()
    except (ValueError, TypeError):
        return None


def register_view(request: HttpRequest) -> HttpResponse:
    next_url = safe_next_url(
        request,
        request.GET.get("next") or request.POST.get("next"),
        fallback=reverse("customers:dashboard"),
    )
    if request.user.is_authenticated:
        return redirect(next_url)
    form = CustomerRegistrationForm(request.POST or None)
    if form.is_valid():
        user = form.save()
        login(request, user, backend=_CUSTOMER_AUTH_BACKEND)
        messages.success(request, customer_welcome_message(user))
        return redirect(next_url)
    return render(
        request,
        "customers/register.html",
        {"form": form, "today": date.today().isoformat(), "next": request.GET.get("next", "")},
    )


@require_http_methods(["GET", "POST"])
def register_modal_view(request: HttpRequest) -> HttpResponse:
    """HTMX partial — registration modal; redirects to *next* on success."""
    next_url = safe_next_url(
        request,
        request.GET.get("next") or request.POST.get("next"),
        fallback=reverse("customers:dashboard"),
    )
    if request.user.is_authenticated:
        response = HttpResponse(status=204)
        response["HX-Redirect"] = htmx_redirect_url(next_url)
        return response

    form = CustomerRegistrationForm(request.POST or None)
    product = _product_from_request(request)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend=_CUSTOMER_AUTH_BACKEND)
        context: dict = {}
        if product:
            context.update(_reviews_context(request, product))
        response = render(request, "customers/register_modal_success.html", context)
        response["HX-Reswap"] = "none"
        return _hx_trigger(
            response,
            {
                "modalClose": True,
                "toast": {"message": customer_welcome_message(user), "type": "success"},
                "svitik": svitik_event(
                    str(_("Радий вас бачити! Збирайте монети за покупки та обмінюйте їх на купони.")),
                    variant="welcome",
                    title=str(_("Привіт, %(name)s!") % {"name": customer_display_name(user)}),
                ),
            },
        )

    product_id = product.pk if product else None
    return render(
        request,
        "customers/register_modal.html",
        {
            "form": form,
            "next": next_url,
            "today": date.today().isoformat(),
            "product_id": product_id,
        },
    )


def login_view(request: HttpRequest) -> HttpResponse:
    next_url = safe_next_url(
        request,
        request.GET.get("next") or request.POST.get("next"),
        fallback=reverse("customers:dashboard"),
    )
    if request.user.is_authenticated:
        return redirect(next_url)
    form = CustomerLoginForm(request, request.POST or None)
    if form.is_valid():
        login(request, form.get_user(), backend=_CUSTOMER_AUTH_BACKEND)
        return redirect(next_url)
    next_param = request.POST.get("next") or request.GET.get("next", "")
    return render(request, "customers/login.html", {"form": form, "next": next_param})


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("/")


@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
    from apps.core.debug_i18n_log import log_request_i18n
    from apps.loyalty.coins import total_pending_coins

    log_request_i18n(request, view="dashboard")
    return render(
        request,
        "customers/dashboard.html",
        {"pending_coins": total_pending_coins(request.user)},
    )


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
