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
from apps.promotions.services import with_active_promotions

from .cross_sell import suggested_products_for_category, suggested_products_for_product
from .gallery import product_gallery_urls
from .models import Brand, Category, Product
from .services import (
    cached_product_count,
    category_listing_category_scope,
    category_listing_products,
    finalize_product_listing,
    get_brands_for_category,
    get_category_facets,
    get_filtered_products,
    get_product_facets,
    get_sale_products_queryset,
    order_stock_first,
    visible_catalog_products,
)
from .facet_cache import catalog_filter_params, count_cache_key, facet_cache_key


def home_view(request: HttpRequest) -> HttpResponse:
    from .home_cache import get_home_view_context

    return render(request, "catalog/home.html", get_home_view_context())


def category_view(request: HttpRequest, slug: str) -> HttpResponse:
    category = get_object_or_404(Category, slug=slug, is_active=True)
    from apps.core.used_category import is_used_category_branch

    if is_used_category_branch(category):
        raise Http404

    from .nav import get_subtree_product_counts

    # htmx-запити (пагінація/фільтри) не показують підкатегорії, тож для них
    # рахуємо лише поточну категорію (як і раніше) — 1 запит. Для звичайного
    # показу сторінки підкатегорії потрібні однаково, тож рахуємо їх разом з
    # категорією ОДНИМ запитом get_subtree_product_counts замість двох
    # окремих раунд-трипів до БД (перевірка 404 + підрахунок підкатегорій).
    if request.htmx:
        subcategories_all: list[Category] = []
        subtree_counts = get_subtree_product_counts({category.pk})
    else:
        subcategories_all = list(
            category.get_children().filter(is_active=True).order_by("sort_order", "name"),
        )
        subtree_counts = get_subtree_product_counts({category.pk, *(c.pk for c in subcategories_all)})

    if subtree_counts.get(category.pk, 0) == 0:
        raise Http404

    base_qs = category_listing_products(category)
    cat_scope = category_listing_category_scope(category)

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
    count_key = count_cache_key(scope="category-v2", scope_id=category.pk, params=filter_params)

    # Фільтри будуються один раз: qs_lite — для count і фасетів,
    # finalize_product_listing — доводить той самий queryset для сторінки.
    qs_lite = get_filtered_products(
        base_qs,
        brand_ids,
        filter_ids,
        price_min,
        price_max,
        in_stock,
        sort,
        for_count=True,
        skip_image_filter=True,
    )
    total = cached_product_count(qs_lite, cache_key=count_key)

    qs = with_active_promotions(finalize_product_listing(qs_lite, sort))
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
    brands = get_brands_for_category(cat_scope, category_id=category.pk)

    subcategories = [c for c in subcategories_all if subtree_counts.get(c.pk, 0) > 0]
    category_ancestors = list(category.get_ancestors())

    suggested_products: list[Product] = []
    suggested_cross_sell = False
    if page == 1:
        suggested_products, suggested_cross_sell = suggested_products_for_category(category)

    ctx = {
        "category": category,
        "category_ancestors": category_ancestors,
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
        "suggested_products": suggested_products,
        "suggested_cross_sell": suggested_cross_sell,
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
            .prefetch_related("images", "attributes__attribute__group", "categories")
        ),
        slug=slug,
    )
    from apps.catalog.view_counter import bump_product_view

    bump_product_view(product.pk)

    category_pks = [category.pk for category in product.categories.all()]
    related, suggested_cross_sell = suggested_products_for_product(product)

    primary_category = product.categories.all()[0] if category_pks else None
    category_ancestors = list(primary_category.get_ancestors()) if primary_category else []

    attrs_by_group: dict = {}
    for pa in product.attributes.select_related("attribute__group").order_by("attribute__group__sort_order", "attribute__sort_order"):
        g = pa.attribute.group
        if g.pk not in attrs_by_group:
            attrs_by_group[g.pk] = {"group": g, "items": []}
        attrs_by_group[g.pk]["items"].append(pa)

    promotion = None
    active_promotions = getattr(product, "active_promotions", None)
    if active_promotions:
        promotion = active_promotions[0]
    timer_end = None
    if promotion:
        timer_end = promotion.end_date
    elif product.sale_timer_active:
        timer_end = product.sale_end_date

    return render(request, "catalog/product_detail.html", {
        "product": product,
        "primary_category": primary_category,
        "category_ancestors": category_ancestors,
        "gallery_urls": product_gallery_urls(product),
        "attrs_by_group": attrs_by_group.values(),
        "related": related,
        "suggested_cross_sell": suggested_cross_sell,
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

    base_qs = brand.products.filter(is_visible=True, has_display_image=True)
    qs_lite = get_filtered_products(
        base_qs,
        filters=filter_ids,
        price_min=price_min,
        price_max=price_max,
        in_stock_only=in_stock,
        sort=sort,
        for_count=True,
        skip_image_filter=True,
    )
    total = cached_product_count(qs_lite, cache_key=count_key)

    qs = with_active_promotions(finalize_product_listing(qs_lite, sort))
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


@cache_page(600)
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
    from django.core.cache import cache

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
    count_key = "catalog:sale:total_count"
    total = cache.get(count_key)
    if total is None:
        total = qs.count()
        cache.set(count_key, total, 300)
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


def product_listing_image_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Cached WebP thumbnail for product cards (Brain/external URLs)."""
    from django.http import FileResponse, Http404, HttpResponseRedirect
    from django.templatetags.static import static

    from apps.catalog.gallery import resolve_product_image_url
    from apps.catalog.listing_image import ensure_listing_webp
    from apps.catalog.models import Product

    product = Product.objects.filter(pk=pk, is_visible=True).first()
    if not product:
        raise Http404

    if product.image:
        return HttpResponseRedirect(product.image_thumb.url)

    path = ensure_listing_webp(product)
    if path:
        response = FileResponse(path.open("rb"), content_type="image/webp")
        response["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    # Серверний фетч не вдався (напр. постачальник тимчасово блокує IP серверу
    # за 403) — та ж сама зовнішня URL зазвичай доступна напряму з браузера
    # клієнта (як на сторінці товару), тож віддаємо її замість заглушки.
    # Короткий кеш (не HTTP-кеш) — фолбек не позначаємо тривалим Cache-Control,
    # бо джерело може знову стати доступним і webp-кеш підхопиться сам.
    source_url = resolve_product_image_url(product)
    if source_url:
        return HttpResponseRedirect(source_url)

    return HttpResponseRedirect(static("images/no-photo.svg"))
