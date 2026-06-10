"""Merge duplicate OpenCart filter groups and filter values by normalized name."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Count, Model, QuerySet

from apps.catalog.ru_localization import merge_scoped_records

logger = logging.getLogger(__name__)

_BRAND_GROUP_NAMES = frozenset({"Виробник", "Производитель"})


def normalized_label(obj: Model, field: str = "name") -> str:
    uk = (getattr(obj, f"{field}_uk", None) or "").strip()
    base = uk or (getattr(obj, field) or "").strip()
    return base.casefold()


@dataclass
class DedupeStats:
    groups_merged: int = 0
    groups_removed: int = 0
    filters_merged: int = 0
    filters_moved: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "groups_merged": self.groups_merged,
            "groups_removed": self.groups_removed,
            "filters_merged": self.filters_merged,
            "filters_moved": self.filters_moved,
        }


def _group_link_count(qs: QuerySet) -> QuerySet:
    return qs.annotate(_link_count=Count("filters__productfilter", distinct=True))


def _filter_link_count(qs: QuerySet) -> QuerySet:
    return qs.annotate(_link_count=Count("productfilter", distinct=True))


def dedupe_catalog_filters(*, dry_run: bool = False) -> DedupeStats:
    from apps.catalog.models import Filter, FilterGroup, ProductFilter

    stats = DedupeStats()

    groups = list(
        _group_link_count(FilterGroup.objects.all()).order_by("-_link_count", "pk"),
    )
    by_group_name: dict[str, list] = defaultdict(list)
    for group in groups:
        by_group_name[normalized_label(group)].append(group)

    with transaction.atomic():
        for group_list in by_group_name.values():
            if len(group_list) <= 1:
                continue

            keep = group_list[0]
            keep_filters: dict[str, int] = {
                normalized_label(f): f.pk
                for f in Filter.objects.filter(group_id=keep.pk).only("pk", "name", "name_uk")
            }
            keep_is_brand = keep.is_brand or normalized_label(keep) in {
                n.casefold() for n in _BRAND_GROUP_NAMES
            }

            for drop in group_list[1:]:
                drop_filters = list(
                    _filter_link_count(Filter.objects.filter(group_id=drop.pk)).order_by(
                        "-_link_count",
                        "pk",
                    ),
                )
                for filt in drop_filters:
                    norm = normalized_label(filt)
                    keep_pk = keep_filters.get(norm)
                    if keep_pk:
                        if not dry_run:
                            merge_scoped_records(
                                Filter,
                                keep_pk=keep_pk,
                                drop_pk=filt.pk,
                                link_model=ProductFilter,
                                fk_name="filter_id",
                            )
                        stats.filters_merged += 1
                    else:
                        if not dry_run:
                            filt.group_id = keep.pk
                            filt.save(update_fields=["group_id"])
                        keep_filters[norm] = filt.pk
                        stats.filters_moved += 1

                if drop.is_brand:
                    keep_is_brand = True

                if not dry_run:
                    drop.delete()
                stats.groups_removed += 1
                stats.groups_merged += 1

            if keep_is_brand and not keep.is_brand and not dry_run:
                keep.is_brand = True
                keep.save(update_fields=["is_brand"])

        stats.filters_merged += _dedupe_filters_within_groups(
            Filter,
            ProductFilter,
            dry_run=dry_run,
        )

    logger.info("dedupe_catalog_filters: %s dry_run=%s", stats.as_dict(), dry_run)
    return stats


def _dedupe_filters_within_groups(
    filter_model: type[Model],
    link_model: type[Model],
    *,
    dry_run: bool,
) -> int:
    merged = 0
    filters = list(
        _filter_link_count(filter_model.objects.select_related("group")).order_by(
            "group_id",
            "-_link_count",
            "pk",
        ),
    )
    by_scope: dict[tuple[int, str], list] = defaultdict(list)
    for filt in filters:
        by_scope[(filt.group_id, normalized_label(filt))].append(filt)

    for flist in by_scope.values():
        if len(flist) <= 1:
            continue
        keep_pk = flist[0].pk
        for drop in flist[1:]:
            if not dry_run:
                merge_scoped_records(
                    filter_model,
                    keep_pk=keep_pk,
                    drop_pk=drop.pk,
                    link_model=link_model,
                    fk_name="filter_id",
                )
            merged += 1

    return merged
