"""Search views: full-text results page + HTMX live dropdown."""

from __future__ import annotations

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector, TrigramSimilarity
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.catalog.models import Category, Product
from apps.catalog.services import order_stock_first


def _search_qs(q: str):
    """Run FTS + trigram fallback."""
    if not q:
        return Product.objects.none()

    vector = SearchVector("name", weight="A") + SearchVector("sku", weight="A") + SearchVector("description", weight="B")
    query = SearchQuery(q, config="ukrainian")

    fts_qs = (
        Product.objects.annotate(rank=SearchRank(vector, query))
        .filter(is_visible=True, rank__gte=0.01)
        .select_related("brand")
    )

    if fts_qs.exists():
        return order_stock_first(fts_qs, "-rank")[:48]

    # Fallback: trigram icontains
    return order_stock_first(
        Product.objects.filter(
            Q(name__icontains=q) | Q(sku__icontains=q) | Q(brand__name__icontains=q),
            is_visible=True,
        )
        .select_related("brand")
        .distinct(),
        "name",
    )[:48]


def results_view(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    products = _search_qs(q) if q else Product.objects.none()
    return render(request, "search/results.html", {
        "q": q,
        "products": products,
        "total": products.count() if q else 0,
        "top_categories": Category.objects.filter(is_active=True, is_top=True, level=0).order_by("sort_order")[:12],
    })


def live_search_view(request: HttpRequest) -> HttpResponse:
    """HTMX partial — live dropdown results (max 6 items)."""
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return HttpResponse("")

    products = _search_qs(q)[:6]
    return render(request, "search/live_results.html", {"q": q, "products": products})
