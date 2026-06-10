from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from .forms import ReturnRequestForm
from .models import InfoPage
from .services import notify_return_request


def page_detail_view(request: HttpRequest, slug: str) -> HttpResponse:
    page = get_object_or_404(InfoPage, slug=slug, is_active=True)
    return render(request, "pages/detail.html", {"page": page})


def delivery_view(request: HttpRequest) -> HttpResponse:
    page = InfoPage.objects.filter(slug=InfoPage.SLUG_DELIVERY, is_active=True).first()
    return render(request, "pages/delivery.html", {"page": page})


def payment_view(request: HttpRequest) -> HttpResponse:
    page = InfoPage.objects.filter(slug=InfoPage.SLUG_PAYMENT, is_active=True).first()
    return render(request, "pages/payment.html", {"page": page})


def warranty_view(request: HttpRequest) -> HttpResponse:
    page = InfoPage.objects.filter(slug=InfoPage.SLUG_WARRANTY, is_active=True).first()
    return render(request, "pages/detail.html", {"page": page})


@require_http_methods(["GET", "POST"])
def returns_view(request: HttpRequest) -> HttpResponse:
    page = InfoPage.objects.filter(slug=InfoPage.SLUG_RETURNS, is_active=True).first()
    form = ReturnRequestForm()

    if request.method == "POST":
        form = ReturnRequestForm(request.POST, request.FILES)
        if form.is_valid():
            claim = form.save()
            notify_return_request(claim)
            messages.success(
                request,
                _("Дякуємо! Заявку надіслано. Менеджер зв'яжеться з вами найближчим часом."),
            )
            return redirect("pages:returns")

    return render(
        request,
        "pages/returns.html",
        {
            "page": page,
            "form": form,
        },
    )


def contact_view(request: HttpRequest) -> HttpResponse:
    page = InfoPage.objects.filter(slug=InfoPage.SLUG_CONTACT, is_active=True).first()
    return render(request, "pages/contact.html", {"page": page})


def privacy_view(request: HttpRequest) -> HttpResponse:
    page = InfoPage.objects.filter(slug=InfoPage.SLUG_PRIVACY, is_active=True).first()
    return render(request, "pages/detail.html", {"page": page})
