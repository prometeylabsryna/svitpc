from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.catalog.models import Product

COMPARE_KEY = "svitpc_compare"
MAX_COMPARE = 4


def _build_attr_groups(products: list) -> list[dict]:
    """
    Returns attribute groups for the compare table.
    Each group: {"name": str, "rows": [{"name": str, "values": [str, ...]}, ...]}
    Rows are sorted by group/attribute sort_order; missing values are "—".
    """
    # key: (group_sort, group_name, attr_sort, attr_name) -> {product_pk: value}
    attr_map: dict[tuple, dict[int, str]] = {}
    for product in products:
        for pa in product.attributes.all():
            attr = pa.attribute
            key = (attr.group.sort_order, attr.group.name, attr.sort_order, attr.name)
            attr_map.setdefault(key, {})[product.pk] = pa.value

    groups: dict[tuple, list] = {}
    for key in sorted(attr_map):
        g_sort, g_name, _a_sort, a_name = key
        group_key = (g_sort, g_name)
        groups.setdefault(group_key, []).append({
            "name": a_name,
            "values": [attr_map[key].get(p.pk, "—") for p in products],
        })

    return [{"name": g_name, "rows": rows} for (_g_sort, g_name), rows in groups.items()]


def compare_page_view(request: HttpRequest) -> HttpResponse:
    ids = request.session.get(COMPARE_KEY, [])
    products = list(
        Product.objects.filter(pk__in=ids, is_visible=True)
        .select_related("brand")
        .prefetch_related("attributes__attribute__group")
    )
    attr_groups = _build_attr_groups(products)
    return render(request, "compare/compare.html", {"products": products, "attr_groups": attr_groups})


@require_POST
def toggle_view(request: HttpRequest, product_id: int) -> HttpResponse:
    ids: list = list(request.session.get(COMPARE_KEY, []))
    if product_id in ids:
        ids.remove(product_id)
    elif len(ids) < MAX_COMPARE:
        ids.append(product_id)
    request.session[COMPARE_KEY] = ids
    count = len(ids)
    response = HttpResponse(status=204)
    response["HX-Trigger"] = f'{{"compareUpdated": {count}}}'
    return response
