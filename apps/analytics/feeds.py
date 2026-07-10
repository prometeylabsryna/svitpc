"""Shared product feed queryset and diagnostics for Google Merchant Center."""

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


def visible_products_queryset() -> QuerySet[Product]:
    return (
        Product.objects.filter(is_visible=True)
        .select_related("brand")
        .prefetch_related("categories")
    )


def _merchant_base() -> QuerySet[Product]:
    return visible_products_queryset().filter(stock__gt=0).order_by("pk")


def feed_category_ids() -> list[int]:
    """PK усіх категорій (+ підкатегорій) з ANALYTICS_FEED_CATEGORY_SLUGS.

    MPTT-дерево не гарантує, що товари прив'язані саме до кореневих категорій
    (найчастіше — до листових підкатегорій), тож для кожного кореня беремо
    get_descendants(include_self=True), а не сам корінь.
    """
    from apps.catalog.models import Category

    slugs = getattr(settings, "ANALYTICS_FEED_CATEGORY_SLUGS", [])
    ids: set[int] = set()
    for root in Category.objects.filter(slug__in=slugs):
        ids.update(root.get_descendants(include_self=True).values_list("pk", flat=True))
    return list(ids)


def merchant_feed_queryset() -> QuerySet[Product]:
    """Visible in-stock products from ANALYTICS_FEED_CATEGORY_SLUGS categories.

    Обмежено ANALYTICS_FEED_MAX_PRODUCTS — за вимогою фід охоплює лише
    ноутбуки/комп'ютери/комплектуючі, а не весь каталог.
    """
    max_items = getattr(settings, "ANALYTICS_FEED_MAX_PRODUCTS", 10000)
    qs = _merchant_base().filter(categories__in=feed_category_ids()).distinct()
    return qs[:max_items]


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
    merchant_issues: tuple[FeedIssueStat, ...]


FEED_DEFINITIONS: tuple[FeedDefinition, ...] = (
    FeedDefinition(
        slug=FEED_MERCHANT_SLUG,
        title="Google Merchant Center — ноутбуки, комп'ютери, комплектуючі",
        description=(
            "Товарний фід для Shopping / Performance Max. Лише видимі товари в наявності "
            "з категорій «Ноутбуки, планшети», «Комп'ютери, аксесуари», «Комплектуючі до ПК» "
            "(з підкатегоріями). Максимум 10 000 товарів."
        ),
        queryset_builder="merchant",
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


_FEED_STATS_CACHE_KEY = "analytics:feed_stats_v3"
_FEED_STATS_CACHE_TTL = 300  # 5 minutes


def _compute_feed_stats(site_url: str) -> FeedStats:
    max_items = getattr(settings, "ANALYTICS_FEED_MAX_PRODUCTS", 10000)
    visible = Product.objects.filter(is_visible=True)
    merchant_eligible_qs = visible.filter(stock__gt=0, categories__in=feed_category_ids()).distinct()
    visible_count = visible.count()
    merchant_eligible = merchant_eligible_qs.count()

    return FeedStats(
        site_url=site_url,
        max_products=max_items,
        visible_products=visible_count,
        merchant_eligible=merchant_eligible,
        merchant_in_feed=min(merchant_eligible, max_items),
        merchant_issues=_issue_stats(merchant_eligible_qs),
    )


def collect_feed_stats(request: HttpRequest | None = None) -> FeedStats:
    from django.core.cache import cache

    site_url = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    if not site_url and request is not None:
        site_url = f"{request.scheme}://{request.get_host()}"

    cached = cache.get(_FEED_STATS_CACHE_KEY)
    if cached is not None:
        return cached

    stats = _compute_feed_stats(site_url)
    cache.set(_FEED_STATS_CACHE_KEY, stats, _FEED_STATS_CACHE_TTL)
    return stats
