"""Backfill django-modeltranslation ``*_uk`` columns from legacy base columns."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import connection


@dataclass(frozen=True)
class BackfillSpec:
    table: str
    legacy_column: str
    uk_column: str


CATALOG_BACKFILL_SPECS: tuple[BackfillSpec, ...] = (
    BackfillSpec("catalog_productattribute", "value", "value_uk"),
    BackfillSpec("catalog_brand", "name", "name_uk"),
)


def backfill_uk_from_legacy(
    specs: tuple[BackfillSpec, ...] = CATALOG_BACKFILL_SPECS,
) -> dict[str, int]:
    """Copy non-empty legacy columns into empty ``*_uk`` translation columns."""
    stats: dict[str, int] = {}
    with connection.cursor() as cursor:
        for spec in specs:
            cursor.execute(
                f"""
                UPDATE {spec.table}
                SET {spec.uk_column} = {spec.legacy_column}
                WHERE ({spec.uk_column} IS NULL OR {spec.uk_column} = '')
                  AND {spec.legacy_column} IS NOT NULL
                  AND {spec.legacy_column} != ''
                """
            )
            stats[f"{spec.table}.{spec.uk_column}"] = cursor.rowcount
    return stats
