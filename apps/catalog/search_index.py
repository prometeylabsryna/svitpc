"""Precomputed PostgreSQL full-text search vectors for catalog products."""

from __future__ import annotations

from django.conf import settings
from django.contrib.postgres.search import SearchVector
from django.db import connection
from django.db.models import QuerySet, Value

from apps.catalog.models import Brand, Product
from apps.core.text import unescape_legacy_html

_TABLE_COLUMNS: dict[str, frozenset[str]] | None = None


def _table_columns(table: str) -> frozenset[str]:
    global _TABLE_COLUMNS
    if _TABLE_COLUMNS is None:
        _TABLE_COLUMNS = {}
    if table not in _TABLE_COLUMNS:
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, table)
        _TABLE_COLUMNS[table] = frozenset(col.name for col in description)
    return _TABLE_COLUMNS[table]


def _product_column(name: str) -> bool:
    return name in _table_columns("catalog_product")


def _brand_column(name: str) -> bool:
    return name in _table_columns("catalog_brand")


def product_only_search_vector_expression() -> SearchVector:
    """SearchVector over Product columns only (safe for ``QuerySet.update``)."""
    config = settings.POSTGRES_FTS_CONFIG
    parts: list[SearchVector] = [
        SearchVector("name", weight="A", config=config),
        SearchVector("sku", weight="A", config=config),
        SearchVector("model", weight="B", config=config),
    ]
    for field in ("name_uk", "name_en"):
        if _product_column(field):
            parts.append(SearchVector(field, weight="A", config=config))
    for field in ("short_description", "short_description_uk", "short_description_en"):
        if _product_column(field):
            parts.append(SearchVector(field, weight="B", config=config))
    for field in ("description", "description_uk", "description_en"):
        if _product_column(field):
            parts.append(SearchVector(field, weight="C", config=config))

    combined = parts[0]
    for part in parts[1:]:
        combined = combined + part
    return combined


def _brand_value_vectors(brand: Brand | None) -> SearchVector | None:
    if brand is None:
        return None
    config = settings.POSTGRES_FTS_CONFIG
    parts: list[SearchVector] = []
    for field in ("name", "name_uk", "name_en"):
        if not _brand_column(field):
            continue
        text = unescape_legacy_html((getattr(brand, field, None) or "").strip())
        if text:
            parts.append(SearchVector(Value(text), weight="A", config=config))
    if not parts:
        return None
    combined = parts[0]
    for part in parts[1:]:
        combined = combined + part
    return combined


def _merge_brand_vectors_sql(product_ids: list[int] | None = None) -> int:
    """Append brand name tokens via UPDATE … FROM (bulk-safe)."""
    brand_fields = [f for f in ("name", "name_uk", "name_en") if _brand_column(f)]
    if not brand_fields:
        return 0

    config = settings.POSTGRES_FTS_CONFIG
    brand_expr = " || ".join(
        f"setweight(to_tsvector(%s, coalesce(b.{field}, '')), 'A')" for field in brand_fields
    )
    params: list = [config] * len(brand_fields)
    id_filter = ""
    if product_ids is not None:
        id_filter = "AND p.id = ANY(%s)"
        params.append(product_ids)

    sql = (
        "UPDATE catalog_product AS p "
        "SET search_vector = COALESCE(p.search_vector, ''::tsvector) || ("
        + brand_expr
        + ") FROM catalog_brand AS b WHERE p.brand_id = b.id "
        + id_filter
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.rowcount


def refresh_product_search_vectors(queryset: QuerySet[Product] | None = None) -> int:
    """Recompute ``search_vector`` for the given queryset (or all products)."""
    qs = queryset if queryset is not None else Product.objects.all()
    pks = list(qs.values_list("pk", flat=True))
    if not pks:
        return 0

    if len(pks) == 1:
        product = Product.objects.select_related("brand").filter(pk=pks[0]).first()
        if product is None:
            return 0
        vector = product_only_search_vector_expression()
        brand_vector = _brand_value_vectors(product.brand)
        if brand_vector is not None:
            vector = vector + brand_vector
        return Product.objects.filter(pk=product.pk).update(search_vector=vector)

    Product.objects.filter(pk__in=pks).update(search_vector=product_only_search_vector_expression())
    return _merge_brand_vectors_sql(pks)


def refresh_products_for_brand(brand_id: int) -> int:
    return refresh_product_search_vectors(Product.objects.filter(brand_id=brand_id))
