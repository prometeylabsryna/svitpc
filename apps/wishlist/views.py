import json

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.catalog.models import Product
from apps.promotions.services import with_active_promotions

from .models import WishlistItem

_SESSION_KEY = "wishlist"


def _guest_ids(request: HttpRequest) -> list[int]:
    return request.session.get(_SESSION_KEY, [])


def _guest_toggle(request: HttpRequest, product_id: int) -> tuple[bool, int]:
    """Toggle product in session wishlist. Returns (added, count)."""
    ids: list[int] = request.session.get(_SESSION_KEY, [])[:]
    if product_id in ids:
        ids.remove(product_id)
        added = False
    else:
        ids.append(product_id)
        added = True
    request.session[_SESSION_KEY] = ids
    request.session.modified = True
    return added, len(ids)


def wishlist_page_view(request: HttpRequest) -> HttpResponse:
    from apps.core.debug_i18n_log import log_request_i18n

    log_request_i18n(request, view="wishlist_page")
    if request.user.is_authenticated:
        items = (
            request.user.wishlist
            .select_related("product__brand")
            .prefetch_related("product__images")
            .order_by("-added_at")
        )
        product_qs = with_active_promotions(Product.objects.filter(
            pk__in=[item.product_id for item in items],
            is_visible=True,
        ).select_related("brand").prefetch_related("images"))
        product_map = {p.pk: p for p in product_qs}
        products = [product_map[item.product_id] for item in items if item.product_id in product_map]
    else:
        ids = _guest_ids(request)
        products = list(
            with_active_promotions(
                Product.objects.filter(pk__in=ids, is_visible=True).select_related("brand").prefetch_related("images")
            )
        )
    return render(request, "wishlist/wishlist.html", {"products": products})


@require_POST
def toggle_view(request: HttpRequest, product_id: int) -> HttpResponse:
    product = get_object_or_404(Product, pk=product_id)
    if request.user.is_authenticated:
        item, created = WishlistItem.objects.get_or_create(customer=request.user, product=product)
        if not created:
            item.delete()
        count = request.user.wishlist.count()
    else:
        created, count = _guest_toggle(request, product.pk)
    message = _("Товар додано до бажаних") if created else _("Прибрано з бажаних")
    response = HttpResponse(status=204)
    response["HX-Trigger"] = json.dumps(
        {
            "wishlistUpdated": count,
            "wishlistActive": created,
            "toast": {"message": message, "type": "success"},
        },
        ensure_ascii=True,
    )
    return response
