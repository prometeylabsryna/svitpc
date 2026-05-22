"""Catalog views: home, category, product detail, brand, specials."""

from __future__ import annotations

from decimal import Decimal

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import cache_page
from django_htmx.http import trigger_client_event

from django.db.models import Avg, Count, Q

from .gallery import product_gallery_urls
from .models import Brand, Category, Product
from .services import get_category_facets, get_filtered_products, get_product_facets, order_stock_first


def _top_categories_qs():
    """Top-level categories for navigation. Falls back to all level=0 active when none flagged."""
    qs = Category.objects.filter(is_active=True, level=0)
    flagged = qs.filter(is_top=True).order_by("sort_order", "name")
    return flagged if flagged.exists() else qs.order_by("sort_order", "name")


def home_view(request: HttpRequest) -> HttpResponse:
    top_categories = _top_categories_qs()[:12]

    visible = Product.objects.filter(is_visible=True).select_related("brand")

    new_products = order_stock_first(visible.filter(is_new=True), "sort_order", "name")[:6]
    if not new_products:
        new_products = order_stock_first(visible, "-date_added", "-pk")[:6]

    hit_products = order_stock_first(visible.filter(is_hit=True), "-viewed", "sort_order")[:6]
    if not hit_products:
        hit_products = order_stock_first(visible, "-viewed", "-pk")[:6]

    sale_products = order_stock_first(visible.filter(old_price__isnull=False), "sort_order", "name")[:6]

    return render(request, "catalog/home.html", {
        "top_categories": top_categories,
        "new_products": new_products,
        "hit_products": hit_products,
        "sale_products": sale_products,
    })


def category_view(request: HttpRequest, slug: str) -> HttpResponse:
    category = get_object_or_404(Category, slug=slug, is_active=True)
    # Descendants included
    cats = category.get_descendants(include_self=True)
    base_qs = Product.objects.filter(categories__in=cats, is_visible=True).distinct()

    # Parse filters from GET
    brand_ids = [int(x) for x in request.GET.getlist("brand") if x.isdigit()]
    filter_ids = [int(x) for x in request.GET.getlist("f") if x.isdigit()]
    price_min = Decimal(request.GET["price_min"]) if request.GET.get("price_min") else None
    price_max = Decimal(request.GET["price_max"]) if request.GET.get("price_max") else None
    sort = request.GET.get("sort", "default")
    in_stock = bool(request.GET.get("in_stock"))
    page = int(request.GET.get("page", 1))
    per_page = 24

    qs = get_filtered_products(base_qs, brand_ids, filter_ids, price_min, price_max, in_stock, sort)
    total = qs.count()
    products = qs[(page - 1) * per_page: page * per_page]

    facets = get_category_facets(category, qs)
    for _gdata in facets.values():
        _gdata["has_active"] = any(opt["id"] in filter_ids for opt in _gdata["options"])
    brands = Brand.objects.filter(products__categories__in=cats, products__is_visible=True).distinct()

    _qp = request.GET.copy()
    _qp.pop("page", None)

    ctx = {
        "category": category,
        "products": products,
        "facets": facets,
        "brands": brands,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
        "sort": sort,
        "selected_brands": brand_ids,
        "selected_filters": filter_ids,
        "price_min": price_min,
        "price_max": price_max,
        "in_stock": in_stock,
        "query_params": _qp.urlencode(),
        "top_categories": _top_categories_qs()[:12],
    }

    # HTMX partial — only product grid
    if request.htmx:
        return render(request, "catalog/partials/product_grid.html", ctx)

    return render(request, "catalog/category.html", ctx)


def product_detail_view(request: HttpRequest, slug: str) -> HttpResponse:
    _approved = Q(reviews__is_approved=True)
    product = get_object_or_404(
        Product.objects
        .annotate(
            avg_rating_ann=Avg("reviews__rating", filter=_approved),
            review_count_ann=Count("reviews", filter=_approved),
        )
        .select_related("brand")
        .prefetch_related("images", "attributes__attribute__group"),
        slug=slug,
        is_visible=True,
    )
    # Increment viewed
    Product.objects.filter(pk=product.pk).update(viewed=product.viewed + 1)

    related = order_stock_first(
        Product.objects.filter(
            categories__in=product.categories.all(), is_visible=True
        ).exclude(pk=product.pk).select_related("brand").distinct(),
        "sort_order",
    )[:6]

    attrs_by_group: dict = {}
    for pa in product.attributes.select_related("attribute__group").order_by("attribute__group__sort_order", "attribute__sort_order"):
        g = pa.attribute.group
        if g.pk not in attrs_by_group:
            attrs_by_group[g.pk] = {"group": g, "items": []}
        attrs_by_group[g.pk]["items"].append(pa)

    return render(request, "catalog/product_detail.html", {
        "product": product,
        "gallery_urls": product_gallery_urls(product),
        "attrs_by_group": attrs_by_group.values(),
        "related": related,
        "top_categories": _top_categories_qs()[:12],
    })


def brand_view(request: HttpRequest, slug: str) -> HttpResponse:
    brand = get_object_or_404(Brand, slug=slug)
    page = int(request.GET.get("page", 1))
    per_page = 24
    sort = request.GET.get("sort", "default")

    filter_ids = [int(x) for x in request.GET.getlist("f") if x.isdigit()]
    price_min = Decimal(request.GET["price_min"]) if request.GET.get("price_min") else None
    price_max = Decimal(request.GET["price_max"]) if request.GET.get("price_max") else None
    in_stock = bool(request.GET.get("in_stock"))

    base_qs = brand.products.filter(is_visible=True)
    qs = get_filtered_products(base_qs, filters=filter_ids, price_min=price_min, price_max=price_max, in_stock_only=in_stock, sort=sort)
    total = qs.count()
    products = qs[(page - 1) * per_page: page * per_page]

    facets = get_product_facets(qs)
    for _gdata in facets.values():
        _gdata["has_active"] = any(opt["id"] in filter_ids for opt in _gdata["options"])

    _qp = request.GET.copy()
    _qp.pop("page", None)

    ctx = {
        "brand": brand,
        "products": products,
        "facets": facets,
        "brands": [],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
        "sort": sort,
        "selected_brands": [],
        "selected_filters": filter_ids,
        "price_min": price_min,
        "price_max": price_max,
        "in_stock": in_stock,
        "query_params": _qp.urlencode(),
        "top_categories": _top_categories_qs()[:12],
    }

    if request.htmx:
        return render(request, "catalog/partials/product_grid.html", ctx)
    return render(request, "catalog/brand.html", ctx)


def brands_list_view(request: HttpRequest) -> HttpResponse:
    brands = Brand.objects.all().order_by("name")
    return render(request, "catalog/brands.html", {
        "brands": brands,
        "top_categories": _top_categories_qs()[:12],
    })


@cache_page(300)
def new_products_view(request: HttpRequest) -> HttpResponse:
    qs = Product.objects.filter(is_visible=True).select_related("brand")
    products = order_stock_first(qs.filter(is_new=True), "sort_order", "name")[:24]
    if not products:
        products = order_stock_first(qs, "-date_added", "-pk")[:24]
    return render(request, "catalog/product_list.html", {
        "title": "Новинки",
        "products": products,
        "top_categories": _top_categories_qs()[:12],
    })


@cache_page(300)
def hit_products_view(request: HttpRequest) -> HttpResponse:
    qs = Product.objects.filter(is_visible=True).select_related("brand")
    products = order_stock_first(qs.filter(is_hit=True), "-viewed", "sort_order")[:24]
    if not products:
        products = order_stock_first(qs, "-viewed", "-pk")[:24]
    return render(request, "catalog/product_list.html", {
        "title": "Хіти продажів",
        "products": products,
        "top_categories": _top_categories_qs()[:12],
    })


def sale_products_view(request: HttpRequest) -> HttpResponse:
    qs = Product.objects.filter(is_visible=True, old_price__isnull=False).select_related("brand")
    products = order_stock_first(qs, "sort_order", "name")
    return render(request, "catalog/product_list.html", {
        "title": "Акції та знижки",
        "products": products,
        "top_categories": _top_categories_qs()[:12],
    })
