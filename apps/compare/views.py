import json
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.catalog.models import Product
from apps.core.i18n import localized_field

COMPARE_KEY = "svitpc_compare"
MAX_COMPARE = 4
EMPTY = "—"


def _display(text: str) -> str:
    t = (text or "").strip()
    return t if t else EMPTY


def _loc(obj: object, field: str) -> str:
    return localized_field(obj, field) or str(getattr(obj, field, "") or "")


def _build_attr_groups(products: list[Product]) -> list[dict[str, Any]]:
    """
    Build compare table groups from product filters and attributes.
    Filters (OpenCart oc_product_filter) often hold values while attribute text is empty.
    """
    filter_rows: dict[str, dict[str, Any]] = {}
    for product in products:
        for pf in product.filters.all():
            group = pf.filter.group
            filt = pf.filter
            row_name = _loc(group, "name") or group.name
            key = row_name.strip().casefold()
            if key not in filter_rows:
                filter_rows[key] = {
                    "sort": (group.sort_order, filt.sort_order),
                    "name": row_name,
                    "values": {},
                }
            filter_rows[key]["values"][product.pk] = _display(_loc(filt, "name") or filt.name)

    attr_map: dict[tuple, dict[int, str]] = {}
    for product in products:
        for pa in product.attributes.all():
            val = _display(_loc(pa, "value"))
            if val == EMPTY:
                continue
            attr = pa.attribute
            attr_name = _loc(attr, "name") or attr.name
            key = (attr.group.sort_order, _loc(attr.group, "name") or attr.group.name, attr.sort_order, attr_name)
            attr_map.setdefault(key, {})[product.pk] = val

    groups: list[dict[str, Any]] = []
    if filter_rows:
        rows = [
            {
                "name": row["name"],
                "values": [row["values"].get(p.pk, EMPTY) for p in products],
            }
            for row in sorted(filter_rows.values(), key=lambda r: r["sort"])
        ]
        groups.append({"name": "", "rows": rows})

    attr_groups: dict[tuple, list] = {}
    for key in sorted(attr_map):
        g_sort, g_name, _a_sort, a_name = key
        group_key = (g_sort, g_name)
        attr_groups.setdefault(group_key, []).append({
            "name": a_name,
            "values": [attr_map[key].get(p.pk, EMPTY) for p in products],
        })

    groups.extend([{"name": g_name, "rows": rows} for (_g_sort, g_name), rows in attr_groups.items()])
    return groups


def _compare_response(
    request: HttpRequest,
    count: int,
    *,
    compare_active: bool | None = None,
    toast_message: str | None = None,
    toast_type: str = "success",
) -> HttpResponse:
    payload: dict[str, object] = {"compareUpdated": count}
    if compare_active is not None:
        payload["compareActive"] = compare_active
    if toast_message:
        payload["toast"] = {"message": toast_message, "type": toast_type}
    response = HttpResponse(status=204)
    # ASCII-only JSON so the header is not RFC 2047–encoded (breaks JSON.parse in JS).
    response["HX-Trigger"] = json.dumps(payload, ensure_ascii=True)
    if request.headers.get("HX-Request") and "/compare" in request.headers.get("HX-Current-URL", ""):
        response["HX-Redirect"] = reverse("compare:page")
    return response


def compare_page_view(request: HttpRequest) -> HttpResponse:
    ids = request.session.get(COMPARE_KEY, [])
    products = list(
        Product.objects.filter(pk__in=ids, is_visible=True)
        .select_related("brand")
        .prefetch_related(
            "attributes__attribute__group",
            "filters__filter__group",
        )
    )
    attr_groups = _build_attr_groups(products)
    return render(request, "compare/compare.html", {"products": products, "attr_groups": attr_groups})


@require_POST
def toggle_view(request: HttpRequest, product_id: int) -> HttpResponse:
    ids: list = list(request.session.get(COMPARE_KEY, []))
    if product_id in ids:
        ids.remove(product_id)
        active = False
        message = _("Прибрано з порівняння")
    elif len(ids) < MAX_COMPARE:
        ids.append(product_id)
        active = True
        message = _("Додано до порівняння")
    else:
        return _compare_response(
            request,
            len(ids),
            compare_active=False,
            toast_message=_("У порівнянні вже максимум 4 товари"),
            toast_type="warning",
        )
    request.session[COMPARE_KEY] = ids
    request.session.modified = True
    return _compare_response(request, len(ids), compare_active=active, toast_message=message)


@require_POST
def clear_view(request: HttpRequest) -> HttpResponse:
    request.session[COMPARE_KEY] = []
    request.session.modified = True
    return _compare_response(request, 0, toast_message=_("Порівняння очищено"))
