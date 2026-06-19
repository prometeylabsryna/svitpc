"""Catalog views: home, category, product detail, brand, specials."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Avg, Count, Q
from django.http import HttpRequest, HttpResponse
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_page

from apps.analytics.ecommerce import product_list_payload, product_view_payload
from apps.core.svitik import product_purchase_tip
from apps.promotions.models import Promotion
from apps.promotions.services import with_active_promotions

from .gallery import filter_products_with_display_image, product_gallery_urls
from .models import Brand, Category, Product
from .services import (
    cached_product_count,
    get_brands_for_category,
    get_category_facets,
    get_filtered_products,
    get_product_facets,
    get_sale_products_queryset,
    order_stock_first,
    visible_catalog_products,
)
from .facet_cache import catalog_filter_params, count_cache_key, facet_cache_key
from .home_cache import get_home_hit_products, get_home_new_products, get_home_sale_products


def home_view(request: HttpRequest) -> HttpResponse:
    from apps.promotions.home_ads import (
        active_home_banners,
        get_home_ad_settings,
        recommended_banner_size,
    )

    home_ad_settings = get_home_ad_settings()
    home_ads = list(active_home_banners())
    home_ad_columns = home_ad_settings.visible_columns
    slot_w, slot_h = recommended_banner_size(home_ad_columns)
    home_ads_carousel = len(home_ads) > home_ad_columns

    from apps.services.querysets import home_featured_services

    return render(request, "catalog/home.html", {
        "new_products": get_home_new_products(),
        "hit_products": get_home_hit_products(),
        "sale_products": get_home_sale_products(),
        "home_services": list(home_featured_services()),
        "home_ads": home_ads,
        "home_ad_columns": home_ad_columns,
        "home_ad_slot_width": slot_w,
        "home_ad_slot_height": slot_h,
        "home_ads_carousel": home_ads_carousel,
    })


def category_view(request: HttpRequest, slug: str) -> HttpResponse:
    category = get_object_or_404(Category, slug=slug, is_active=True)
    from apps.core.used_category import is_used_category_branch

    if is_used_category_branch(category):
        raise Http404
    # Descendants included
    cats = category.get_descendants(include_self=True)
    base_qs = visible_catalog_products().filter(categories__in=cats).distinct()

    # Parse filters from GET
    brand_ids = [int(x) for x in request.GET.getlist("brand") if x.isdigit()]
    filter_ids = [int(x) for x in request.GET.getlist("f") if x.isdigit()]
    price_min = Decimal(request.GET["price_min"]) if request.GET.get("price_min") else None
    price_max = Decimal(request.GET["price_max"]) if request.GET.get("price_max") else None
    sort = request.GET.get("sort", "default")
    in_stock = bool(request.GET.get("in_stock"))
    page = int(request.GET.get("page", 1))
    per_page = 24

    filter_params = catalog_filter_params(
        brand_ids=brand_ids,
        filter_ids=filter_ids,
        price_min=price_min,
        price_max=price_max,
        in_stock=in_stock,
        sort=sort,
    )
    count_key = count_cache_key(scope="category", scope_id=category.pk, params=filter_params)

    qs_lite = with_active_promotions(
        get_filtered_products(
            base_qs,
            brand_ids,
            filter_ids,
            price_min,
            price_max,
            in_stock,
            sort,
            for_count=True,
        )
    )
    total = cached_product_count(qs_lite, cache_key=count_key)

    qs = with_active_promotions(
        get_filtered_products(
            base_qs,
            brand_ids,
            filter_ids,
            price_min,
            price_max,
            in_stock,
            sort,
        )
    )
    products = qs[(page - 1) * per_page: page * per_page]

    _qp = request.GET.copy()
    _qp.pop("page", None)

    if request.htmx:
        ctx = {
            "products": products,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
            "query_params": _qp.urlencode(),
        }
        return render(request, "catalog/partials/product_grid.html", ctx)

    facets = get_category_facets(category, qs_lite, filter_params=filter_params)
    for _gdata in facets.values():
        _gdata["has_active"] = any(opt["id"] in filter_ids for opt in _gdata["options"])
    brands = get_brands_for_category(cats, category_id=category.pk)
    subcategories = category.get_children().filter(is_active=True).order_by("sort_order", "name")

    ctx = {
        "category": category,
        "subcategories": subcategories,
        "products": products,
        "ecommerce_list": product_list_payload(
            list_id=f"category-{category.pk}",
            list_name=category.name,
            products=products,
        ),
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
    }

    return render(request, "catalog/category.html", ctx)


def product_detail_view(request: HttpRequest, slug: str) -> HttpResponse:
    _approved = Q(reviews__is_approved=True)
    # Allow direct links to out-of-stock Brain items (is_visible=False when hide_if_out_of_stock).
    product = get_object_or_404(
        with_active_promotions(
            Product.objects.annotate(
                avg_rating_ann=Avg("reviews__rating", filter=_approved),
                review_count_ann=Count("reviews", filter=_approved),
            )
            .select_related("brand")
            .prefetch_related("images", "attributes__attribute__group")
        ),
        slug=slug,
    )
    # Increment viewed
    Product.objects.filter(pk=product.pk).update(viewed=product.viewed + 1)

    related = order_stock_first(
        with_active_promotions(
            visible_catalog_products().filter(
                categories__in=product.categories.all(),
            ).exclude(pk=product.pk).select_related("brand").distinct()
        ),
        "sort_order",
    )[:6]

    attrs_by_group: dict = {}
    for pa in product.attributes.select_related("attribute__group").order_by("attribute__group__sort_order", "attribute__sort_order"):
        g = pa.attribute.group
        if g.pk not in attrs_by_group:
            attrs_by_group[g.pk] = {"group": g, "items": []}
        attrs_by_group[g.pk]["items"].append(pa)

    from django.utils import timezone

    now = timezone.now()
    promotion = Promotion.objects.filter(
        product=product,
        is_active=True,
        start_date__lte=now,
        end_date__gte=now,
    ).first()
    timer_end = None
    if promotion:
        timer_end = promotion.end_date
    elif product.sale_timer_active:
        timer_end = product.sale_end_date

    return render(request, "catalog/product_detail.html", {
        "product": product,
        "gallery_urls": product_gallery_urls(product),
        "attrs_by_group": attrs_by_group.values(),
        "related": related,
        "ecommerce_product": product_view_payload(product),
        "svitik_tip": product_purchase_tip(product),
        "promotion": promotion,
        "timer_end": timer_end,
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

    filter_params = catalog_filter_params(
        brand_ids=[],
        filter_ids=filter_ids,
        price_min=price_min,
        price_max=price_max,
        in_stock=in_stock,
        sort=sort,
    )
    count_key = count_cache_key(scope="brand", scope_id=brand.pk, params=filter_params)
    facet_key = facet_cache_key(scope="brand", scope_id=brand.pk, params=filter_params)

    base_qs = filter_products_with_display_image(brand.products.filter(is_visible=True))
    qs_lite = with_active_promotions(
        get_filtered_products(
            base_qs,
            filters=filter_ids,
            price_min=price_min,
            price_max=price_max,
            in_stock_only=in_stock,
            sort=sort,
            for_count=True,
        )
    )
    total = cached_product_count(qs_lite, cache_key=count_key)

    qs = with_active_promotions(
        get_filtered_products(
            base_qs,
            filters=filter_ids,
            price_min=price_min,
            price_max=price_max,
            in_stock_only=in_stock,
            sort=sort,
        )
    )
    products = qs[(page - 1) * per_page: page * per_page]

    _qp = request.GET.copy()
    _qp.pop("page", None)

    if request.htmx:
        ctx = {
            "products": products,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
            "query_params": _qp.urlencode(),
        }
        return render(request, "catalog/partials/product_grid.html", ctx)

    facets = get_product_facets(qs_lite, cache_key=facet_key)
    for _gdata in facets.values():
        _gdata["has_active"] = any(opt["id"] in filter_ids for opt in _gdata["options"])

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
    }

    return render(request, "catalog/brand.html", ctx)


def brands_list_view(request: HttpRequest) -> HttpResponse:
    brands = Brand.objects.all().order_by("name")
    return render(request, "catalog/brands.html", {"brands": brands})


@cache_page(300)
def new_products_view(request: HttpRequest) -> HttpResponse:
    qs = with_active_promotions(
        visible_catalog_products().select_related("brand").prefetch_related("images")
    )
    products = order_stock_first(qs.filter(is_new=True), "sort_order", "name")[:24]
    if not products:
        products = order_stock_first(qs, "-date_added", "-pk")[:24]
    return render(request, "catalog/product_list.html", {
        "title": _("Новинки"),
        "products": products,
    })


@cache_page(300)
def hit_products_view(request: HttpRequest) -> HttpResponse:
    qs = with_active_promotions(
        visible_catalog_products().select_related("brand").prefetch_related("images")
    )
    products = order_stock_first(qs.filter(is_hit=True), "-viewed", "sort_order")[:24]
    if not products:
        products = order_stock_first(qs, "-viewed", "-pk")[:24]
    return render(request, "catalog/product_list.html", {
        "title": _("Хіти продажів"),
        "products": products,
    })


@cache_page(300)
def sale_products_view(request: HttpRequest) -> HttpResponse:
    per_page = 24
    try:
        page = max(1, int(request.GET.get("page", 1) or 1))
    except (TypeError, ValueError):
        page = 1

    qs = order_stock_first(
        with_active_promotions(get_sale_products_queryset()),
        "sort_order",
        "name",
    )
    total = qs.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    products = qs[(page - 1) * per_page : page * per_page]

    return render(
        request,
        "catalog/product_list.html",
        {
            "title": _("Акції та знижки"),
            "products": products,
            "show_promotions_link": True,
            "page": page,
            "total_pages": total_pages,
            "query_params": "",
        },
    )
