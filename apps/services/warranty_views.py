"""Warranty claim views — public form for service requests."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.catalog.models import Product

from .decorators import staff_service_required
from .forms import WarrantyClaimForm
from .serial_lookup import lookup_serial, product_to_lookup_payload, search_products
from .warranty_models import ProductSerial, WarrantyClaim


def _warranty_form_initial(request: HttpRequest) -> dict:
    initial: dict = {}
    sn = request.GET.get("serial", "").strip()
    if not sn:
        return initial
    data = lookup_serial(sn)
    if not data.found:
        return initial
    initial = data.as_dict()
    initial.pop("found", None)
    initial.pop("warranty_status_label", None)
    initial["product_serial"] = data.product_serial_id
    return initial


def _save_warranty_claim(request: HttpRequest, form: WarrantyClaimForm) -> WarrantyClaim:
    claim = form.save(commit=False)
    if request.user.is_authenticated:
        claim.created_by = request.user
    ps_id = request.POST.get("product_serial_id")
    if ps_id:
        claim.product_serial_id = int(ps_id)
    elif claim.serial_number:
        record = ProductSerial.objects.filter(serial_number__iexact=claim.serial_number).first()
        if record:
            claim.product_serial = record

    action = request.POST.get("action", "submit")
    if not request.user.is_staff:
        action = "submit"
    if action == "submit":
        claim.status = WarrantyClaim.STATUS_SUBMITTED
        claim.submitted_at = timezone.now()
    else:
        claim.status = WarrantyClaim.STATUS_DRAFT

    claim.save()
    claim.assign_rma_number()
    if claim.rma_number:
        claim.save(update_fields=["rma_number"])
    return claim


@require_http_methods(["GET", "POST"])
def warranty_list_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = WarrantyClaimForm(request.POST)
        if form.is_valid():
            claim = _save_warranty_claim(request, form)
            if claim.status == WarrantyClaim.STATUS_SUBMITTED:
                return render(
                    request,
                    "services/warranty_list.html",
                    {"submitted_claim": claim},
                )
            return redirect("services:warranty_list")
        return render(
            request,
            "services/warranty_list.html",
            {"form": form},
            status=400,
        )

    form = WarrantyClaimForm(initial=_warranty_form_initial(request))
    return render(request, "services/warranty_list.html", {"form": form})


def warranty_create_view(request: HttpRequest) -> HttpResponse:
    return redirect("services:warranty_list")


@require_GET
def warranty_serial_lookup_view(request: HttpRequest) -> JsonResponse:
    serial = request.GET.get("serial", "")
    return JsonResponse(lookup_serial(serial).as_dict())


@require_GET
def warranty_product_search_view(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q") or request.GET.get("product_name", "")
    products = search_products(query)
    return render(
        request,
        "services/partials/warranty_product_results.html",
        {"products": products, "query": query},
    )


@require_GET
def warranty_product_pick_view(request: HttpRequest, pk: int) -> JsonResponse:
    product = get_object_or_404(Product, pk=pk)
    payload = product_to_lookup_payload(product)
    months = None
    attr = product.attributes.select_related("attribute").filter(attribute__name__icontains="Гарант").first()
    if attr:
        try:
            months = int("".join(c for c in attr.value if c.isdigit())[:3])
        except ValueError:
            months = None
    if months:
        from datetime import timedelta

        until = timezone.localdate() + timedelta(days=months * 30)
        payload["warranty_until"] = until.isoformat()
        payload["is_under_warranty"] = True
        payload["warranty_status_label"] = str(_("Товар гарантійний"))
    return JsonResponse(payload)


@staff_service_required
@require_POST
def warranty_claim_submit_view(request: HttpRequest, pk: int) -> HttpResponse:
    claim = get_object_or_404(WarrantyClaim, pk=pk)
    claim.status = WarrantyClaim.STATUS_SUBMITTED
    claim.submitted_at = timezone.now()
    claim.save(update_fields=["status", "submitted_at", "updated_at"])
    if not claim.rma_number:
        claim.assign_rma_number()
        claim.save(update_fields=["rma_number"])
    return redirect("services:warranty_list")
