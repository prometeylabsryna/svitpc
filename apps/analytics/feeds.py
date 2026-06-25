"""Shared product feed querysets and diagnostics for Google Merchant / Ads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models import Count, Q, QuerySet

from apps.catalog.gallery import PLACEHOLDER_URL_IREGEX, STALE_URL_IREGEX
from apps.catalog.models import Product

if TYPE_CHECKING:
    from django.http import HttpRequest

FEED_MERCHANT_SLUG = "google-merchant"
FEED_REMARKETING_SLUG = "google-ads"


def visible_products_queryset() -> QuerySet[Product]:
    return (
        Product.objects.filter(is_visible=True)
        .select_related("brand")
        .prefetch_related("categories")
    )


def merchant_feed_queryset() -> QuerySet[Product]:
    max_items = getattr(settings, "ANALYTICS_FEED_MAX_PRODUCTS", 10000)
    return visible_products_queryset().filter(stock__gt=0).order_by("pk")[:max_items]


def remarketing_feed_queryset() -> QuerySet[Product]:
    max_items = getattr(settings, "ANALYTICS_FEED_MAX_PRODUCTS", 10000)
    return visible_products_queryset().order_by("pk")[:max_items]


def _invalid_image_q() -> Q:
    return (
        Q(image_url="")
        | Q(image_url__isnull=True)
        | Q(image_url__iregex=PLACEHOLDER_URL_IREGEX)
        | Q(image_url__iregex=STALE_URL_IREGEX)
    )


def _empty_text_q(field: str) -> Q:
    return Q(**{field: ""}) | Q(**{f"{field}__isnull": True})


@dataclass(frozen=True)
class FeedDefinition:
    slug: str
    title: str
    description: str
    queryset_builder: str  # key for template / stats


@dataclass(frozen=True)
class FeedIssueStat:
    label: str
    count: int
    hint: str


@dataclass(frozen=True)
class FeedStats:
    site_url: str
    max_products: int
    visible_products: int
    merchant_eligible: int
    merchant_in_feed: int
    remarketing_in_feed: int
    merchant_issues: tuple[FeedIssueStat, ...]
    remarketing_issues: tuple[FeedIssueStat, ...]


FEED_DEFINITIONS: tuple[FeedDefinition, ...] = (
    FeedDefinition(
        slug=FEED_MERCHANT_SLUG,
        title="Google Merchant Center",
        description="Основний товарний фід для Shopping / Performance Max. Лише видимі товари в наявності.",
        queryset_builder="merchant",
    ),
    FeedDefinition(
        slug=FEED_REMARKETING_SLUG,
        title="Google Ads — динамічний ремаркетинг",
        description="Фід для динамічних оголошень і ремаркетингу. Включає товари без залишку.",
        queryset_builder="remarketing",
    ),
)


def feed_path(slug: str) -> str:
    return f"/feeds/{slug}.xml"


def absolute_feed_url(request: HttpRequest | None, slug: str) -> str:
    site = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    path = feed_path(slug)
    if site:
        return f"{site}{path}"
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def _issue_stats(qs: QuerySet[Product]) -> tuple[FeedIssueStat, ...]:
    no_description = qs.filter(
        _empty_text_q("short_description"),
        _empty_text_q("description"),
    ).count()
    no_brand = qs.filter(brand__isnull=True).count()
    no_category = qs.annotate(_cat_count=Count("categories")).filter(_cat_count=0).count()
    no_image = qs.filter(_invalid_image_q()).count()
    no_sku = qs.filter(_empty_text_q("sku")).count()

    return (
        FeedIssueStat(
            label="Без опису",
            count=no_description,
            hint="Заповніть короткий або повний опис — Google вимагає g:description.",
        ),
        FeedIssueStat(
            label="Без зображення",
            count=no_image,
            hint="Потрібне валідне g:image_link (не placeholder і не застаріле OpenCart-фото).",
        ),
        FeedIssueStat(
            label="Без бренду",
            count=no_brand,
            hint="Для більшості категорій Google вимагає g:brand.",
        ),
        FeedIssueStat(
            label="Без категорії",
            count=no_category,
            hint="g:product_type формується з дерева категорій сайту.",
        ),
        FeedIssueStat(
            label="Без артикулу / MPN",
            count=no_sku,
            hint="Рекомендовано g:mpn; GTIN — якщо штрихкод 12–13 символів.",
        ),
    )


def collect_feed_stats(request: HttpRequest | None = None) -> FeedStats:
    max_items = getattr(settings, "ANALYTICS_FEED_MAX_PRODUCTS", 10000)
    site_url = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    if not site_url and request is not None:
        site_url = f"{request.scheme}://{request.get_host()}"

    visible = Product.objects.filter(is_visible=True)
    merchant_base = visible.filter(stock__gt=0)
    visible_count = visible.count()
    merchant_eligible = merchant_base.count()

    return FeedStats(
        site_url=site_url,
        max_products=max_items,
        visible_products=visible_count,
        merchant_eligible=merchant_eligible,
        merchant_in_feed=min(merchant_eligible, max_items),
        remarketing_in_feed=min(visible_count, max_items),
        merchant_issues=_issue_stats(merchant_base),
        remarketing_issues=_issue_stats(visible),
    )
