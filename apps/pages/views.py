from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import InfoPage


def page_detail_view(request: HttpRequest, slug: str) -> HttpResponse:
    page = get_object_or_404(InfoPage, slug=slug, is_active=True)
    return render(request, "pages/detail.html", {"page": page})


def delivery_view(request: HttpRequest) -> HttpResponse:
    page = InfoPage.objects.filter(slug=InfoPage.SLUG_DELIVERY, is_active=True).first()
    return render(request, "pages/detail.html", {"page": page})


def payment_view(request: HttpRequest) -> HttpResponse:
    page = InfoPage.objects.filter(slug=InfoPage.SLUG_PAYMENT, is_active=True).first()
    return render(request, "pages/detail.html", {"page": page})


def warranty_view(request: HttpRequest) -> HttpResponse:
    page = InfoPage.objects.filter(slug=InfoPage.SLUG_WARRANTY, is_active=True).first()
    return render(request, "pages/detail.html", {"page": page})


def returns_view(request: HttpRequest) -> HttpResponse:
    page = InfoPage.objects.filter(slug=InfoPage.SLUG_RETURNS, is_active=True).first()
    return render(request, "pages/detail.html", {"page": page})


def contact_view(request: HttpRequest) -> HttpResponse:
    page = InfoPage.objects.filter(slug=InfoPage.SLUG_CONTACT, is_active=True).first()
    return render(request, "pages/contact.html", {"page": page})


def privacy_view(request: HttpRequest) -> HttpResponse:
    page = InfoPage.objects.filter(slug=InfoPage.SLUG_PRIVACY, is_active=True).first()
    return render(request, "pages/detail.html", {"page": page})
