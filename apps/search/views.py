"""Search views: full-text results page + HTMX live dropdown."""

from __future__ import annotations

import re
import unicodedata

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.catalog.models import Product
from apps.catalog.services import order_stock_first, visible_catalog_products
from apps.promotions.services import with_active_promotions

_SEARCH_LIMIT = 48
_LIVE_LIMIT = 6
_RANK_THRESHOLD = 0.01

_APOSTROPHE_CHARS = "'\u2018\u2019\u201a\u201b\u2032`´\u02bc\u02bb"
_HTML_APOS_ENTITY = "&#039;"
_COMPUTER_WORD = re.compile(r"(?i)компютер")
_LETTER_VARIANTS = (("и", "і"), ("і", "и"), ("е", "є"), ("є", "е"))

_TABLE_COLUMNS: dict[str, frozenset[str]] = {}


def _table_columns(table: str) -> frozenset[str]:
    if table not in _TABLE_COLUMNS:
        from django.db import connection

        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, table)
        _TABLE_COLUMNS[table] = frozenset(col.name for col in description)
    return _TABLE_COLUMNS[table]


def _search_base_qs():
    return with_active_promotions(
        visible_catalog_products().select_related("brand").prefetch_related("images")
    )


def _search_query(q: str) -> SearchQuery:
    return SearchQuery(q, config=settings.POSTGRES_FTS_CONFIG)


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
            _search_base_qs().filter(_trigram_fallback_q(q)).distinct(),
            "name",
        )[:limit]
    )


def _icontains_fallback_q(q: str) -> Q:
    cond = Q(name__icontains=q) | Q(sku__icontains=q) | Q(model__icontains=q)
    product_cols = _table_columns("catalog_product")
    for field in ("name_uk", "name_en"):
        if field in product_cols:
            cond |= Q(**{f"{field}__icontains": q})
    brand_cols = _table_columns("catalog_brand")
    for field in ("name", "name_uk", "name_en"):
        if field in brand_cols:
            cond |= Q(**{f"brand__{field}__icontains": q})
    return cond


def _fts_results(term: str, *, limit: int) -> list[Product]:
    query = _search_query(term)
    fts_qs = (
        _search_base_qs()
        .filter(search_vector=query)
        .annotate(rank=SearchRank(F("search_vector"), query))
        .filter(rank__gte=_RANK_THRESHOLD)
    )
    return list(order_stock_first(fts_qs, "-rank")[:limit])


def _icontains_results(term: str, *, limit: int) -> list[Product]:
    return list(
        order_stock_first(
            _search_base_qs().filter(_icontains_fallback_q(term)).distinct(),
            "name",
        )[:limit]
    )


def _merge_product_results(*result_lists: list[Product], limit: int) -> list[Product]:
    """Deduplicate by pk, preserving order from the first list that contained each product."""
    seen: set[int] = set()
    merged: list[Product] = []
    for results in result_lists:
        for product in results:
            if product.pk in seen:
                continue
            seen.add(product.pk)
            merged.append(product)
            if len(merged) >= limit:
                return merged
    return merged


def _search_qs(q: str, *, limit: int = _SEARCH_LIMIT) -> list[Product]:
    """FTS → icontains (all spelling variants merged) → trigram fallback."""
    variants = _search_variants(q)
    if not variants:
        return []

    merged = _merge_product_results(
        *(_fts_results(term, limit=limit) for term in variants),
        limit=limit,
    )
    if merged:
        return merged

    merged = _merge_product_results(
        *(_icontains_results(term, limit=limit) for term in variants),
        limit=limit,
    )
    if merged:
        return merged

    return _trigram_fallback(variants[0], limit=limit)


def results_view(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    products = _search_qs(q) if q else []
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
    """HTMX partial — live dropdown results (max 6 items)."""
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return HttpResponse("")

    products = _search_qs(q, limit=_LIVE_LIMIT)
    return render(request, "search/live_results.html", {"q": q, "products": products})
