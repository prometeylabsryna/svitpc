"""Search views: full-text results page + HTMX live dropdown."""

from __future__ import annotations

import re
import unicodedata
from functools import reduce
from operator import or_

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.core.cache import cache
from django.db import DatabaseError
from django.db.models import F, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import translation

from apps.catalog.gallery import _valid_image_url_q
from apps.catalog.models import Product
from apps.catalog.services import order_stock_first
from apps.promotions.services import with_active_promotions

_SEARCH_LIMIT = 48
_LIVE_LIMIT = 6
_RANK_THRESHOLD = 0.01
_LIVE_CACHE_TTL = 180
_RESULTS_CACHE_TTL = 300

_APOSTROPHE_CHARS = "'\u2018\u2019\u201a\u201b\u2032`´\u02bc\u02bb"
_HTML_APOS_ENTITY = "&#039;"
_COMPUTER_WORD = re.compile(r"(?i)компютер")
_LETTER_VARIANTS = (("и", "і"), ("і", "и"), ("е", "є"), ("є", "е"))
_FTS_SUFFIXES = ("ами", "ями", "ів", "ій", "ії", "ии", "і", "и", "ы", "а", "я", "у", "ю")
# Chars unsafe in PostgreSQL tsquery raw mode (- is NOT, | & ! ( ) : * need care).
_TSQUERY_RAW_UNSAFE = re.compile(r"[\s!&|():*\\\-]")

_TABLE_COLUMNS: dict[str, frozenset[str]] = {}


def _table_columns(table: str) -> frozenset[str]:
    if table not in _TABLE_COLUMNS:
        from django.db import connection

        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, table)
        _TABLE_COLUMNS[table] = frozenset(col.name for col in description)
    return _TABLE_COLUMNS[table]


def _search_visible_qs():
    """Visible in-stock rules without gallery EXISTS (fast scan on 200k+ rows)."""
    return Product.objects.filter(is_visible=True).filter(
        Q(stock__gt=0) | Q(hide_if_out_of_stock=False),
    )


def _search_pick_qs():
    """Search candidate set: visible + valid main image URL (no gallery subquery)."""
    return _search_visible_qs().filter(_valid_image_url_q())


def _search_query(q: str) -> SearchQuery:
    return SearchQuery(q, config=settings.POSTGRES_FTS_CONFIG)


def _fts_stem_root(term: str) -> str | None:
    """Rough UA/RU plural stem for prefix FTS (термоси → термос)."""
    if len(term) < 4:
        return None
    for suffix in _FTS_SUFFIXES:
        if len(term) > len(suffix) + 2 and term.casefold().endswith(suffix):
            return term[: -len(suffix)]
    return None


def _fts_tokens(term: str) -> list[str]:
    return [part for part in re.split(r"\s+", term.strip()) if part]


def _safe_raw_prefix_token(token: str) -> bool:
    """Single token without tsquery metacharacters — safe for ``token:*`` raw prefix."""
    return len(token) >= 3 and _TSQUERY_RAW_UNSAFE.search(token) is None


def _fts_queries_for_term(term: str) -> list[SearchQuery]:
    """Plain + prefix FTS queries so plurals match indexed product names."""
    config = settings.POSTGRES_FTS_CONFIG
    seen: set[str] = set()
    queries: list[SearchQuery] = []

    def add(key: str, query: SearchQuery) -> None:
        if key in seen:
            return
        seen.add(key)
        queries.append(query)

    add(f"plain:{term}", SearchQuery(term, config=config))

    tokens = _fts_tokens(term) or [term]
    for token in tokens:
        if token == term:
            continue
        add(f"plain:{token}", SearchQuery(token, config=config))

    for token in tokens:
        if not _safe_raw_prefix_token(token):
            continue
        add(f"prefix:{token}", SearchQuery(f"{token}:*", search_type="raw", config=config))
        root = _fts_stem_root(token)
        if root and root.casefold() != token.casefold() and _safe_raw_prefix_token(root):
            add(f"plain:{root}", SearchQuery(root, config=config))
            add(f"prefix:{root}", SearchQuery(f"{root}:*", search_type="raw", config=config))

    return queries


def _search_cache_key(prefix: str, q: str, limit: int) -> str:
    lang = translation.get_language() or "uk"
    return f"{prefix}:{lang}:{limit}:{q.lower()[:80]}"


def _load_search_products(pks: list[int]) -> list[Product]:
    if not pks:
        return []
    qs = with_active_promotions(
        Product.objects.filter(pk__in=pks, has_display_image=True)
        .select_related("brand")
        .prefetch_related("images")
    )
    pk_map = {p.pk: p for p in qs}
    return [pk_map[pk] for pk in pks if pk in pk_map]


def _search_products_cached(
    q: str,
    *,
    limit: int,
    ttl: int,
    prefix: str,
    fast: bool = False,
) -> list[Product]:
    cache_key = _search_cache_key(prefix, q, limit)
    cached_pks: list[int] | None = cache.get(cache_key)
    if cached_pks is not None:
        return _load_search_products(cached_pks)
    products = _search_qs(q, limit=limit, fast=fast)
    cache.set(cache_key, [p.pk for p in products], ttl)
    return products


def _normalize_search_query(q: str) -> str:
    """Strip noise (extra quotes, alternate apostrophes) before matching."""
    q = unicodedata.normalize("NFKC", q.strip())
    for ch in _APOSTROPHE_CHARS:
        q = q.replace(ch, "'")
    q = q.strip('"').strip()
    while len(q) > 2 and q[-1] in "'\"":
        q = q[:-1].rstrip()
    while len(q) > 2 and q[0] in '"':
        q = q[1:].lstrip()
    return q.strip()


def _html_entity_forms(q: str) -> list[str]:
    """Match OpenCart-imported names where apostrophe is stored as ``&#039;``."""
    forms: list[str] = []
    if "'" in q:
        forms.append(q.replace("'", _HTML_APOS_ENTITY))
    if _HTML_APOS_ENTITY not in q and "'" not in q:
        replaced = _COMPUTER_WORD.sub(f"комп{_HTML_APOS_ENTITY}ютер", q)
        if replaced != q:
            forms.append(replaced)
    return forms


def _search_variants(raw: str) -> list[str]:
    """Normalized query plus common Ukrainian/Russian spelling alternatives."""
    q = _normalize_search_query(raw)
    if not q:
        return []

    variants = [q, *_html_entity_forms(q)]
    bare = q.replace("'", "")
    if bare != q:
        variants.append(bare)
        variants.extend(_html_entity_forms(bare))
    for src, dst in _LETTER_VARIANTS:
        if src in q:
            variants.append(q.replace(src, dst))

    expanded: list[str] = []
    for term in variants:
        expanded.append(term)
        if term and term[0].islower():
            expanded.append(term[0].upper() + term[1:])
    return list(dict.fromkeys(expanded))


def _trigram_fallback_q(q: str) -> Q:
    cond = (
        Q(name__trigram_word_similar=q)
        | Q(sku__trigram_similar=q)
        | Q(model__trigram_word_similar=q)
    )
    product_cols = _table_columns("catalog_product")
    for field in ("name_uk", "name_en"):
        if field in product_cols:
            cond |= Q(**{f"{field}__trigram_word_similar": q})
    brand_cols = _table_columns("catalog_brand")
    for field in ("name", "name_uk", "name_en"):
        if field in brand_cols:
            cond |= Q(**{f"brand__{field}__trigram_word_similar": q})
    return cond


def _trigram_fallback(q: str, *, limit: int) -> list[Product]:
    return list(
        order_stock_first(
            _search_pick_qs().filter(_trigram_fallback_q(q)).distinct(),
            "name",
        )[:limit]
    )


def _fts_results_multi(variants: list[str], *, limit: int) -> list[Product]:
    """Single FTS query for all spelling variants (one DB round-trip)."""
    if not variants:
        return []

    fts_queries: list[SearchQuery] = []
    seen: set[str] = set()
    for term in variants:
        for query in _fts_queries_for_term(term):
            key = str(query)
            if key in seen:
                continue
            seen.add(key)
            fts_queries.append(query)
    if not fts_queries:
        return []

    combined_query = reduce(or_, fts_queries)
    try:
        fts_qs = (
            _search_pick_qs()
            .filter(search_vector=combined_query)
            .annotate(rank=SearchRank(F("search_vector"), combined_query))
            .filter(rank__gte=_RANK_THRESHOLD)
        )
        return list(order_stock_first(fts_qs, "-rank")[:limit])
    except DatabaseError:
        return []


def _search_qs(q: str, *, limit: int = _SEARCH_LIMIT, fast: bool = False) -> list[Product]:
    """FTS (1 query) → trigram fallback.

    icontains-fallback (повний скан таблиці на 35k+ товарів) прибрано:
    trigram-індекси (міграція 0017) покривають опечатки/часткові збіги
    швидше за seq scan. ``fast`` збережено для сумісності викликів.
    """
    variants = _search_variants(q)
    if not variants:
        return []

    results = _fts_results_multi(variants, limit=limit)
    if results:
        return results

    return _trigram_fallback(variants[0], limit=limit)


def results_view(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    if not q:
        return render(request, "search/results.html", {"q": q, "products": [], "total": 0})

    products = _search_products_cached(
        q,
        limit=_SEARCH_LIMIT,
        ttl=_RESULTS_CACHE_TTL,
        prefix="search_results",
        fast=False,
    )
    return render(
        request,
        "search/results.html",
        {
            "q": q,
            "products": products,
            "total": len(products),
        },
    )


def live_search_view(request: HttpRequest) -> HttpResponse:
    """HTMX partial — live dropdown (FTS + trigram only, Redis-cached)."""
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return HttpResponse("")

    products = _search_products_cached(
        q,
        limit=_LIVE_LIMIT,
        ttl=_LIVE_CACHE_TTL,
        prefix="live_search",
        fast=True,
    )
    return render(request, "search/live_results.html", {"q": q, "products": products})
