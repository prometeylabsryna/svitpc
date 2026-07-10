"""Shared product feed querysets and diagnostics for Google Merchant / Ads."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models import Count, Q, QuerySet

from apps.catalog.gallery import PLACEHOLDER_URL_IREGEX, STALE_URL_IREGEX
from apps.catalog.models import Product

if TYPE_CHECKING:
    from django.http import HttpRequest

FEED_MERCHANT_SLUG = "google-merchant"
FEED_REMARKETING_SLUG = "google-ads"
FEED_MERCHANT_CHEAP_SLUG = "google-merchant-cheap"
FEED_MERCHANT_MEDIUM_SLUG = "google-merchant-medium"
FEED_MERCHANT_EXPENSIVE_SLUG = "google-merchant-expensive"

# Price thresholds (UAH): cheap < CHEAP_MAX ≤ medium ≤ EXPENSIVE_MIN < expensive
PRICE_CHEAP_MAX = Decimal("500")
PRICE_EXPENSIVE_MIN = Decimal("5000")


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


def remarketing_feed_queryset() -> QuerySet[Product]:
    """All visible products — no artificial limit."""
    return visible_products_queryset().order_by("pk")


def merchant_feed_cheap_queryset() -> QuerySet[Product]:
    """In-stock products priced below PRICE_CHEAP_MAX."""
    return _merchant_base().filter(price__lt=PRICE_CHEAP_MAX)


def merchant_feed_medium_queryset() -> QuerySet[Product]:
    """In-stock products priced between PRICE_CHEAP_MAX and PRICE_EXPENSIVE_MIN."""
    return _merchant_base().filter(
        price__gte=PRICE_CHEAP_MAX,
        price__lte=PRICE_EXPENSIVE_MIN,
    )


def merchant_feed_expensive_queryset() -> QuerySet[Product]:
    """In-stock products priced above PRICE_EXPENSIVE_MIN."""
    return _merchant_base().filter(price__gt=PRICE_EXPENSIVE_MIN)


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
class PriceTierStat:
    slug: str
    title: str
    description: str
    count: int
    price_range: str


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
    price_tiers: tuple[PriceTierStat, ...]


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


def _price_tier_stats(request: HttpRequest | None) -> tuple[PriceTierStat, ...]:
    cheap_count = merchant_feed_cheap_queryset().count()
    medium_count = merchant_feed_medium_queryset().count()
    expensive_count = merchant_feed_expensive_queryset().count()

    return (
        PriceTierStat(
            slug=FEED_MERCHANT_CHEAP_SLUG,
            title="Merchant — дешеві товари",
            description=f"Товари до {int(PRICE_CHEAP_MAX)} грн. Канцтовари, аксесуари, витратні матеріали.",
            count=cheap_count,
            price_range=f"до {int(PRICE_CHEAP_MAX)} UAH",
        ),
        PriceTierStat(
            slug=FEED_MERCHANT_MEDIUM_SLUG,
            title="Merchant — середній сегмент",
            description=f"Товари {int(PRICE_CHEAP_MAX)}–{int(PRICE_EXPENSIVE_MIN)} грн. Комплектуючі, периферія, принтери.",
            count=medium_count,
            price_range=f"{int(PRICE_CHEAP_MAX)}–{int(PRICE_EXPENSIVE_MIN)} UAH",
        ),
        PriceTierStat(
            slug=FEED_MERCHANT_EXPENSIVE_SLUG,
            title="Merchant — дорогі товари",
            description=f"Товари понад {int(PRICE_EXPENSIVE_MIN)} грн. Ноутбуки, комп'ютери, сервери.",
            count=expensive_count,
            price_range=f"від {int(PRICE_EXPENSIVE_MIN)} UAH",
        ),
    )


_FEED_STATS_CACHE_KEY = "analytics:feed_stats_v2"
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
        remarketing_in_feed=visible_count,
        merchant_issues=_issue_stats(merchant_eligible_qs),
        remarketing_issues=_issue_stats(visible),
        price_tiers=_price_tier_stats(None),
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
